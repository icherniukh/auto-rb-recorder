import os
import tomllib
from dataclasses import dataclass, field


@dataclass
class Config:
    sample_rate: int = 48000
    output_dir: str = field(
        default_factory=lambda: os.path.expanduser("~/Music/auto-rb-recorder")
    )
    silence_threshold_db: float = -50
    min_silence_duration: float = 15
    min_segment_duration: float = 10
    decay_tail: float = 5
    export_format: str = "wav"
    process_name: str = "rekordbox"
    poll_interval: float = 2.0

    @classmethod
    def from_file(cls, path: str) -> "Config":
        with open(path, "rb") as f:
            data = tomllib.load(f)

        cfg = cls()
        rec = data.get("recording", {})
        trig = data.get("trigger", {})
        monitor = data.get("monitor", {})

        if "sample_rate" in rec:
            cfg.sample_rate = rec["sample_rate"]
        if "output_dir" in rec:
            cfg.output_dir = rec["output_dir"]
        if "export_format" in rec:
            cfg.export_format = rec["export_format"]
        if "silence_threshold_db" in trig:
            cfg.silence_threshold_db = trig["silence_threshold_db"]
        if "min_silence_duration" in trig:
            cfg.min_silence_duration = trig["min_silence_duration"]
        if "min_segment_duration" in trig:
            cfg.min_segment_duration = trig["min_segment_duration"]
        if "decay_tail" in trig:
            cfg.decay_tail = trig["decay_tail"]
        if "process_name" in monitor:
            cfg.process_name = monitor["process_name"]
        if "poll_interval" in monitor:
            cfg.poll_interval = monitor["poll_interval"]

        return cfg
