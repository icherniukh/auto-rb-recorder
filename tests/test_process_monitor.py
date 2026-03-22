import unittest
from unittest.mock import patch
from src.process_monitor import ProcessMonitor


class TestProcessMonitor(unittest.TestCase):
    @patch("src.process_monitor.time.sleep")
    @patch("src.process_monitor.ProcessMonitor._find_pid")
    def test_detects_process_start(self, mock_find, mock_sleep):
        # First poll: None. Second poll: None. Third poll: 12345.
        # After startup delay re-check: 12345 (still running).
        mock_find.side_effect = [None, None, 12345, 12345]
        events = []
        mon = ProcessMonitor("rekordbox", poll_interval=0, startup_delay=0)
        mon.on_start = lambda pid: events.append(("start", pid))
        mon.on_stop = lambda: events.append(("stop",))
        for _ in range(3):
            mon.poll_once()
        self.assertEqual(events, [("start", 12345)])

    @patch("src.process_monitor.time.sleep")
    @patch("src.process_monitor.ProcessMonitor._find_pid")
    def test_detects_process_stop(self, mock_find, mock_sleep):
        # Poll 1: 12345 (start), re-check: 12345. Poll 2: 12345. Poll 3: None (stop).
        mock_find.side_effect = [12345, 12345, 12345, None]
        events = []
        mon = ProcessMonitor("rekordbox", poll_interval=0, startup_delay=0)
        mon.on_start = lambda pid: events.append(("start", pid))
        mon.on_stop = lambda: events.append(("stop",))
        for _ in range(3):
            mon.poll_once()
        self.assertEqual(events, [("start", 12345), ("stop",)])

    @patch("src.process_monitor.time.sleep")
    @patch("src.process_monitor.ProcessMonitor._find_pid")
    def test_ignores_duplicate_start(self, mock_find, mock_sleep):
        # Poll 1: 12345 (start), re-check: 12345. Poll 2-3: 12345 (no event).
        mock_find.side_effect = [12345, 12345, 12345, 12345]
        events = []
        mon = ProcessMonitor("rekordbox", poll_interval=0, startup_delay=0)
        mon.on_start = lambda pid: events.append(("start", pid))
        mon.on_stop = lambda: events.append(("stop",))
        for _ in range(3):
            mon.poll_once()
        self.assertEqual(events, [("start", 12345)])

    @patch("src.process_monitor.time.sleep")
    @patch("src.process_monitor.ProcessMonitor._find_pid")
    def test_ignores_transient_process(self, mock_find, mock_sleep):
        # Process appears then disappears during startup delay
        mock_find.side_effect = [12345, None]
        events = []
        mon = ProcessMonitor("rekordbox", poll_interval=0, startup_delay=0)
        mon.on_start = lambda pid: events.append(("start", pid))
        mon.on_stop = lambda: events.append(("stop",))
        mon.poll_once()
        self.assertEqual(events, [])  # No start event fired


if __name__ == "__main__":
    unittest.main()
