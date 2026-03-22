import unittest
from unittest.mock import patch
from src.process_monitor import ProcessMonitor


class TestProcessMonitor(unittest.TestCase):
    @patch("src.process_monitor.ProcessMonitor._find_pid")
    def test_detects_process_start(self, mock_find):
        mock_find.side_effect = [None, None, 12345]
        events = []
        mon = ProcessMonitor("rekordbox", poll_interval=0)
        mon.on_start = lambda pid: events.append(("start", pid))
        mon.on_stop = lambda: events.append(("stop",))
        for _ in range(3):
            mon.poll_once()
        self.assertEqual(events, [("start", 12345)])

    @patch("src.process_monitor.ProcessMonitor._find_pid")
    def test_detects_process_stop(self, mock_find):
        mock_find.side_effect = [12345, 12345, None]
        events = []
        mon = ProcessMonitor("rekordbox", poll_interval=0)
        mon.on_start = lambda pid: events.append(("start", pid))
        mon.on_stop = lambda: events.append(("stop",))
        for _ in range(3):
            mon.poll_once()
        self.assertEqual(events, [("start", 12345), ("stop",)])

    @patch("src.process_monitor.ProcessMonitor._find_pid")
    def test_ignores_duplicate_start(self, mock_find):
        mock_find.side_effect = [12345, 12345, 12345]
        events = []
        mon = ProcessMonitor("rekordbox", poll_interval=0)
        mon.on_start = lambda pid: events.append(("start", pid))
        mon.on_stop = lambda: events.append(("stop",))
        for _ in range(3):
            mon.poll_once()
        self.assertEqual(events, [("start", 12345)])

if __name__ == "__main__":
    unittest.main()
