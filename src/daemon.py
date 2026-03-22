import logging
import os
import signal
import time
from typing import Optional

from src.capture import AudioCapture
from src.config import Config
from src.process_monitor import ProcessMonitor
from src.splitter import SilenceSplitter

log = logging.getLogger("rb-recorder")


class RecorderDaemon:
    def __init__(self, config: Config):
        self.config = config
        self._capture: Optional[AudioCapture] = None
        self._running = False

        self._monitor = ProcessMonitor(
            config.process_name, poll_interval=config.poll_interval
        )
        self._monitor.on_start = self._on_rekordbox_start
        self._monitor.on_stop = self._on_rekordbox_stop

        self._splitter = SilenceSplitter(
            silence_threshold_db=config.silence_threshold_db,
            min_silence_duration=config.min_silence_duration,
            min_segment_duration=config.min_segment_duration,
        )

    def _on_rekordbox_start(self, pid: int):
        log.info(f"Rekordbox detected (PID {pid}). Starting recording.")
        os.makedirs(self.config.output_dir, exist_ok=True)
        self._capture = AudioCapture(
            pid=pid,
            output_dir=self.config.output_dir,
            sample_rate=self.config.sample_rate,
        )
        self._capture.start()

    def _on_rekordbox_stop(self):
        if not self._capture:
            return
        log.info("Rekordbox closed. Stopping recording.")
        output_path = self._capture.stop()
        self._capture = None

        if output_path and os.path.exists(output_path):
            log.info(f"Splitting session: {output_path}")
            files = self._splitter.split(output_path, self.config.output_dir)
            log.info(f"Created {len(files)} set file(s): {files}")

    def run(self):
        self._running = True
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
        log.info("Rekordbox Auto-Recorder armed. Waiting for Rekordbox...")

        while self._running:
            self._monitor.poll_once()
            time.sleep(self.config.poll_interval)

    def _handle_shutdown(self, signum, frame):
        log.info("Shutdown signal received.")
        self._running = False
        self._on_rekordbox_stop()
