import subprocess
import time
from typing import Callable, Optional


class ProcessMonitor:
    def __init__(self, process_name: str, poll_interval: float = 2.0,
                 startup_delay: float = 5.0):
        self.process_name = process_name
        self.poll_interval = poll_interval
        self.startup_delay = startup_delay
        self.on_start: Callable[[int], None] = lambda pid: None
        self.on_stop: Callable[[], None] = lambda: None
        self._current_pid: Optional[int] = None

    def _find_pid(self) -> Optional[int]:
        try:
            result = subprocess.run(
                ["pgrep", "-x", self.process_name],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                return int(result.stdout.strip().split("\n")[0])
        except (ValueError, subprocess.SubprocessError):
            pass
        return None

    def poll_once(self):
        pid = self._find_pid()
        was_running = self._current_pid is not None
        is_running = pid is not None

        if is_running and not was_running:
            # Wait for startup to settle (Rekordbox spawns multiple
            # short-lived processes during launch), then re-check PID
            time.sleep(self.startup_delay)
            pid = self._find_pid()
            if pid is None:
                return  # Process disappeared during startup — ignore
            self._current_pid = pid
            self.on_start(pid)
        elif not is_running and was_running:
            self._current_pid = None
            self.on_stop()
