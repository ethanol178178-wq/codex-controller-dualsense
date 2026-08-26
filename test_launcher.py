import json
import unittest
from unittest.mock import patch

import launcher


class LauncherTests(unittest.TestCase):
    def test_source_runtime_command_reenters_launcher(self):
        with patch.object(launcher.sys, "frozen", False, create=True):
            command = launcher.runtime_command("--service")
        self.assertEqual(command[0], launcher.sys.executable)
        self.assertTrue(command[1].endswith("launcher.py"))
        self.assertEqual(command[-1], "--service")

    def test_status_command_prints_offline_json(self):
        with patch.object(launcher, "service_status", return_value=None), patch("builtins.print") as output:
            result = launcher.main(["--status"])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.call_args.args[0]), {"ok": False})

    def test_default_action_opens_control_center(self):
        with patch.object(launcher, "start_service", return_value=0) as start:
            result = launcher.main([])
        self.assertEqual(result, 0)
        start.assert_called_once_with(open_page=True)

    def test_stop_action_uses_named_event(self):
        with patch.object(launcher, "signal_stop_event", return_value=True):
            self.assertEqual(launcher.main(["--stop"]), 0)


if __name__ == "__main__":
    unittest.main()
