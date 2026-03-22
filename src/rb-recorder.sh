#!/bin/bash
# Rekordbox Auto-Recorder daemon
# Monitors for Rekordbox and captures audio via AudioCapCLI (Core Audio Taps).
set -u

# Defaults (overridable via environment)
OUTPUT_DIR="${RB_RECORDER_OUTPUT_DIR:-$HOME/Music/RekordboxRecordings}"
POLL_INTERVAL="${RB_RECORDER_POLL_INTERVAL:-2}"
SILENCE_THRESHOLD="${RB_RECORDER_SILENCE_THRESHOLD:--50}"
SILENCE_DURATION="${RB_RECORDER_SILENCE_DURATION:-15}"
MIN_SEGMENT="${RB_RECORDER_MIN_SEGMENT:-30}"
SAMPLE_RATE=48000

log() { echo "$(date +%H:%M:%S) [$1] $2"; }

mkdir -p "$OUTPUT_DIR"

# Check prerequisites
command -v AudioCapCLI >/dev/null || { log ERROR "AudioCapCLI not found"; exit 1; }
command -v ffmpeg >/dev/null || { log ERROR "ffmpeg not found"; exit 1; }

CAPTURE_PID=""
RAW_FILE=""
WAV_FILE=""

start_recording() {
    local timestamp
    timestamp=$(date +%Y%m%d_%H%M%S)
    RAW_FILE="$OUTPUT_DIR/.rb_session_${timestamp}.raw"
    WAV_FILE="$OUTPUT_DIR/rb_session_${timestamp}.wav"

    timeout 86400 AudioCapCLI --source rekordbox > "$RAW_FILE" 2>/dev/null &
    CAPTURE_PID=$!
    log INFO "Recording started (PID $CAPTURE_PID) → $RAW_FILE"
}

stop_recording() {
    if [ -n "$CAPTURE_PID" ]; then
        kill "$CAPTURE_PID" 2>/dev/null || true
        wait "$CAPTURE_PID" 2>/dev/null || true
        CAPTURE_PID=""
    fi

    if [ -f "$RAW_FILE" ]; then
        local raw_size
        raw_size=$(wc -c < "$RAW_FILE")
        local duration_s=$((raw_size / SAMPLE_RATE / 2 / 4))
        log INFO "Raw capture: $raw_size bytes (~${duration_s}s)"

        if [ "$raw_size" -gt 0 ]; then
            # Convert raw float32 PCM to 16-bit WAV
            ffmpeg -y -f f32le -ar "$SAMPLE_RATE" -ac 2 \
                -i "$RAW_FILE" -c:a pcm_s16le "$WAV_FILE" 2>/dev/null
            log INFO "Converted to $WAV_FILE"

            # Split by silence
            split_by_silence "$WAV_FILE"
        fi

        rm -f "$RAW_FILE"
    fi
}

split_by_silence() {
    local input="$1"
    local duration
    duration=$(ffprobe -v error -show_entries format=duration \
        -of default=noprint_wrappers=1:nokey=1 "$input" 2>/dev/null) || return

    local stderr
    stderr=$(ffmpeg -i "$input" \
        -af "silencedetect=noise=${SILENCE_THRESHOLD}dB:d=${SILENCE_DURATION}" \
        -f null - 2>&1) || return

    # Parse silence boundaries
    local -a starts ends
    mapfile -t starts < <(echo "$stderr" | grep -o 'silence_start: [0-9.]*' | awk '{print $2}')
    mapfile -t ends < <(echo "$stderr" | grep -o 'silence_end: [0-9.]*' | awk '{print $2}')

    if [ ${#starts[@]} -eq 0 ]; then
        log INFO "No silence detected — keeping single file"
        return
    fi

    local base="${input%.wav}"
    local seg=1

    # Segment before first silence
    local seg_dur
    seg_dur=$(echo "${starts[0]}" | awk '{printf "%.0f", $1}')
    if [ "$seg_dur" -ge "$MIN_SEGMENT" ]; then
        ffmpeg -y -i "$input" -to "${starts[0]}" -c copy \
            "${base}_set$(printf '%02d' $seg).wav" 2>/dev/null
        log INFO "  Set $seg: 0s → ${starts[0]}s"
        seg=$((seg + 1))
    fi

    # Segments between silences
    for i in "${!ends[@]}"; do
        local start="${ends[$i]}"
        local end
        if [ $((i + 1)) -lt ${#starts[@]} ]; then
            end="${starts[$((i + 1))]}"
        else
            end="$duration"
        fi
        seg_dur=$(echo "$end $start" | awk '{printf "%.0f", $1 - $2}')
        if [ "$seg_dur" -ge "$MIN_SEGMENT" ]; then
            ffmpeg -y -i "$input" -ss "$start" -to "$end" -c copy \
                "${base}_set$(printf '%02d' $seg).wav" 2>/dev/null
            log INFO "  Set $seg: ${start}s → ${end}s"
            seg=$((seg + 1))
        fi
    done

    if [ $seg -gt 1 ]; then
        log INFO "Split into $((seg - 1)) set(s)"
        rm -f "$input"  # Remove unsplit original
    fi
}

cleanup() {
    log INFO "Shutdown signal received"
    stop_recording
    exit 0
}
trap cleanup SIGTERM SIGINT

log INFO "Rekordbox Auto-Recorder armed. Waiting for Rekordbox..."

RECORDING=false
while true; do
    if pgrep -x rekordbox >/dev/null 2>&1; then
        if [ "$RECORDING" = false ]; then
            log INFO "Rekordbox detected (PID $(pgrep -x rekordbox | head -1))"
            start_recording
            RECORDING=true
        fi
    else
        if [ "$RECORDING" = true ]; then
            log INFO "Rekordbox closed"
            stop_recording
            RECORDING=false
        fi
    fi
    sleep "$POLL_INTERVAL"
done
