import unittest
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

import bridge
import codex_hook
import serve_ui


class ApiRequestAuthorizationTests(unittest.TestCase):
    def validate(
        self,
        path: str = "/api/mapping",
        origin: str = "http://127.0.0.1:4173",
        content_type: str = "application/json",
        token: str = "",
        expected_token: str = "test-token-that-is-at-least-32-characters",
    ) -> tuple[bridge.HTTPStatus, str] | None:
        return bridge.validate_post_request(path, origin, content_type, token, expected_token)

    def test_allowed_ui_json_request(self) -> None:
        self.assertIsNone(self.validate())

    def test_cross_origin_request_is_rejected(self) -> None:
        result = self.validate(origin="https://example.com")
        self.assertEqual(result[0], bridge.HTTPStatus.FORBIDDEN)

    def test_non_json_request_is_rejected(self) -> None:
        result = self.validate(origin="", content_type="text/plain")
        self.assertEqual(result[0], bridge.HTTPStatus.UNSUPPORTED_MEDIA_TYPE)

    def test_hook_requires_matching_shared_token(self) -> None:
        path = "/api/codex-hook"
        expected = "test-token-that-is-at-least-32-characters"
        self.assertEqual(
            self.validate(path=path, origin="", token="wrong", expected_token=expected)[0],
            bridge.HTTPStatus.UNAUTHORIZED,
        )
        self.assertIsNone(
            self.validate(path=path, origin="", token=expected, expected_token=expected)
        )


class MappingPersistenceTests(unittest.TestCase):
    def test_mapping_survives_bridge_engine_restart(self) -> None:
        # ``TemporaryDirectory`` applies a private ACL on recent Windows
        # Python builds. Restricted test runners can create that directory but
        # cannot write into it, so use an ordinary unique workspace directory.
        directory = Path(__file__).parent / ".test-tmp" / uuid.uuid4().hex
        directory.mkdir(parents=True)
        try:
            path = str(directory / "mapping.json")
            engine = bridge.InputMappingEngine(config_path=path)
            engine.configure({
                "enabled": True,
                "mappings": {"ps": ["CodexFocus"], "cross": ["Enter"]},
                "touchpadGestures": {"enabled": True, "threshold": 320, "muteOnSwitch": False},
            })

            restored = bridge.InputMappingEngine(config_path=path)
            status = restored.status()
            self.assertTrue(status["enabled"])
            self.assertEqual(status["mappings"]["ps"], ["CodexFocus"])
            self.assertEqual(status["mappings"]["cross"], ["Enter"])
        finally:
            shutil.rmtree(directory, ignore_errors=True)


class CodexHookPrivacyTests(unittest.TestCase):
    def test_payload_anonymizes_identifiers_and_omits_content_and_paths(self) -> None:
        source = {
            "session_id": "internal-session-id",
            "turn_id": "internal-turn-id",
            "tool_use_id": "internal-tool-id",
            "last_assistant_message": "private response content",
            "cwd": r"C:\\Users\\Example\\private-project",
            "workspace": r"D:\\confidential",
        }

        payload = codex_hook.build_bridge_payload(source, "PreToolUse")

        self.assertEqual(payload["event"], "PreToolUse")
        self.assertTrue(str(payload["sessionId"]).startswith("anon-"))
        self.assertTrue(str(payload["turnId"]).startswith("anon-"))
        self.assertTrue(str(payload["toolUseId"]).startswith("anon-"))
        self.assertNotIn("internal-session-id", str(payload))
        self.assertNotIn("private response content", str(payload))
        self.assertNotIn("private-project", str(payload))
        self.assertNotIn("lastAssistantMessage", payload)
        self.assertNotIn("cwd", payload)
        self.assertNotIn("workspace", payload)


class PublicUiServerTests(unittest.TestCase):
    def test_public_assets_are_allowlisted(self) -> None:
        index = serve_ui.resolve_asset("/?v=1")
        image = serve_ui.resolve_asset("/assets/dualsense-wireframe.png")

        self.assertTrue(index[0].endswith("index.html"))
        self.assertEqual(index[1], "text/html; charset=utf-8")
        self.assertTrue(image[0].endswith("dualsense-wireframe.png"))
        for request_path in serve_ui.PUBLIC_ASSETS:
            resolved = serve_ui.resolve_asset(request_path)
            self.assertIsNotNone(resolved)
            self.assertTrue(Path(resolved[0]).is_file(), request_path)

    def test_repository_and_traversal_paths_are_not_served(self) -> None:
        self.assertIsNone(serve_ui.resolve_asset("/.git/config"))
        self.assertIsNone(serve_ui.resolve_asset("/README.md"))
        self.assertIsNone(serve_ui.resolve_asset("/%2e%2e/bridge.token"))
        self.assertIsNone(serve_ui.resolve_asset("/web-server.log"))


class ReleaseMetadataTests(unittest.TestCase):
    def test_version_file_matches_bridge_api_version(self) -> None:
        version_file = Path(bridge.__file__).with_name("VERSION")
        self.assertEqual(version_file.read_text(encoding="ascii").strip(), bridge.RELEASE_VERSION)

    def test_required_open_source_documents_exist(self) -> None:
        root = Path(bridge.__file__).parent
        for name in (
            "README.md",
            "LICENSE",
            "THIRD_PARTY_NOTICES.md",
            "PRIVACY.md",
            "CODE_SIGNING_POLICY.md",
            "SIGNING.md",
        ):
            self.assertTrue((root / name).is_file(), name)
        driver_root = root / "driver" / "ds5ptp"
        self.assertTrue((driver_root / "README.md").is_file())
        self.assertTrue((driver_root / "uninstall-driver.ps1").is_file())
        license_root = root / "licenses"
        for name in (
            "CPYTHON-3.12.txt",
            "PYINSTALLER-6.15.txt",
            "INNO-SETUP-6.txt",
        ):
            self.assertTrue((license_root / name).is_file(), name)

    def test_code_signing_policy_is_linked_from_home_page(self) -> None:
        root = Path(bridge.__file__).parent
        readme = (root / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Code signing policy", readme)
        self.assertIn("Free code signing provided by [SignPath.io]", readme)
        self.assertIn("[SignPath Foundation]", readme)
        self.assertIn("PRIVACY.md", readme)
        release_notes = (root / "RELEASE_NOTES.md").read_text(encoding="utf-8")
        self.assertIn("## Code signing policy", release_notes)
        self.assertIn("Version 0.2.4 is unsigned", release_notes)

    def test_release_workflow_refuses_unsigned_publication(self) -> None:
        root = Path(bridge.__file__).parent
        workflow = (root / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("signpath/github-action-submit-signing-request@v2", workflow)
        self.assertEqual(workflow.count("signpath/github-action-submit-signing-request@v2"), 2)
        self.assertIn("verify-signatures.ps1", workflow)
        self.assertIn("Signed release is not configured", workflow)
        self.assertLess(workflow.index("Verify signed release files"), workflow.index("Publish GitHub Release"))

    def test_signed_files_have_release_metadata_configuration(self) -> None:
        root = Path(bridge.__file__).parent
        spec = (root / "packaging" / "DualSenseCodex.spec").read_text(encoding="utf-8")
        installer = (root / "packaging" / "DualSenseCodex.iss").read_text(encoding="utf-8")
        self.assertIn("DUALSENSE_CODEX_VERSION_FILE", spec)
        build_script = (root / "packaging" / "build.ps1").read_text(encoding="utf-8")
        self.assertIn("StringStruct('ProductName', 'Codex Controller for DualSense')", build_script)
        self.assertIn("VersionInfoProductName={#MyAppName}", installer)
        self.assertIn("VersionInfoProductVersion={#MyAppVersion}", installer)


class CodexStatusLightEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = bridge.CodexStatusLightEngine()
        self.engine._apply_if_needed = lambda *_args: None

    def ingest(self, event: str, **extra: object) -> str:
        status = self.engine.ingest({
            "event": event,
            "sessionId": "test-session",
            **extra,
        })
        return str(status["state"])

    def test_tool_boundaries_do_not_end_the_turn(self) -> None:
        self.assertEqual(self.ingest("UserPromptSubmit"), "working")
        self.assertEqual(self.ingest("PreToolUse", toolUseId="tool-1"), "working")
        self.assertEqual(self.ingest("PostToolUse", toolUseId="tool-1"), "working")
        self.assertEqual(self.ingest("PreCompact"), "working")
        self.assertEqual(self.ingest("PreToolUse", toolUseId="tool-2"), "working")
        self.assertEqual(self.ingest("PostToolUse", toolUseId="tool-2"), "working")
        self.assertEqual(self.ingest("Stop"), "complete")

    def test_approved_tool_returns_to_working_until_turn_stops(self) -> None:
        self.assertEqual(self.ingest("UserPromptSubmit"), "working")
        self.assertEqual(
            self.ingest("PermissionRequest", requestKey="approval-1"),
            "approval",
        )
        self.assertEqual(
            self.ingest("PreToolUse", requestKey="approval-1"),
            "working",
        )
        self.assertEqual(
            self.ingest("PostToolUse", requestKey="approval-1"),
            "working",
        )
        self.assertEqual(self.ingest("Stop"), "complete")

    def test_completed_response_text_cannot_create_approval(self) -> None:
        self.assertEqual(self.ingest("UserPromptSubmit"), "working")
        self.assertEqual(
            self.ingest(
                "Stop",
                lastAssistantMessage="已经确认 approval permission 测试通过",
            ),
            "complete",
        )
        self.assertEqual(self.engine.status()["pendingRequests"], 0)

    def test_completion_returns_to_idle_after_micro_feedback_window(self) -> None:
        self.assertEqual(self.ingest("UserPromptSubmit"), "working")
        self.assertEqual(self.ingest("Stop"), "complete")
        with self.engine._lock:
            self.engine._transient_until = bridge.time.time() - 0.01
            self.engine._recompute_locked()
        self.assertEqual(self.engine.status()["state"], "idle")

    def test_failed_turn_uses_error_profile(self) -> None:
        self.assertEqual(self.ingest("UserPromptSubmit"), "working")
        self.assertEqual(self.ingest("Error"), "error")
        self.assertEqual(self.engine.status()["profile"], bridge.CODEX_LIGHT_PROFILES["error"])

    def test_status_does_not_expose_hook_content_or_workspace(self) -> None:
        self.ingest(
            "PreToolUse",
            lastAssistantMessage="private response content",
            workspace=r"C:\\Users\\Example\\private-project",
        )

        status = self.engine.status()
        self.assertNotIn("lastAssistantMessage", status)
        self.assertNotIn("lastHookWorkspace", status)

    def test_new_prompt_clears_legacy_waiting_marker(self) -> None:
        self.engine._sessions["test-session"] = {
            "working": False,
            "pending": {"stop-waiting"},
            "pendingMeta": {"stop-waiting": {}},
            "updatedAt": bridge.time.time(),
        }
        self.engine._recompute_locked()

        self.assertEqual(self.ingest("UserPromptSubmit"), "working")
        self.assertEqual(self.engine.status()["pendingRequests"], 0)

    def test_post_tool_use_resolves_only_matching_concurrent_approval(self) -> None:
        self.assertEqual(self.ingest("PermissionRequest", requestKey="approval-a"), "approval")
        self.assertEqual(self.ingest("PermissionRequest", requestKey="approval-b"), "approval")
        self.assertEqual(self.engine.status()["pendingRequests"], 2)

        self.assertEqual(self.ingest("PostToolUse", requestKey="approval-a"), "approval")
        self.assertEqual(self.engine.status()["pendingRequests"], 1)
        self.assertEqual(self.ingest("PostToolUse", requestKey="approval-b"), "working")
        self.assertEqual(self.engine.status()["pendingRequests"], 0)

    def test_conflicting_request_id_does_not_clear_lone_approval(self) -> None:
        self.assertEqual(self.ingest("PermissionRequest", requestKey="approval-a"), "approval")
        self.assertEqual(self.ingest("PostToolUse", requestKey="approval-b"), "approval")
        self.assertEqual(self.engine.status()["pendingRequests"], 1)

    def test_duplicate_permission_hook_is_idempotent(self) -> None:
        self.assertEqual(self.ingest("PermissionRequest", requestKey="approval-a"), "approval")
        self.assertEqual(self.ingest("PermissionRequest", requestKey="approval-a"), "approval")
        self.assertEqual(self.engine.status()["pendingRequests"], 1)


class AdaptiveTriggerTests(unittest.TestCase):
    class AliveThread:
        @staticmethod
        def is_alive() -> bool:
            return True

    def test_weapon_effect_encoding(self) -> None:
        effect = bridge.build_trigger_effect({
            "mode": "weapon", "start": 3, "end": 6, "strength": 5,
        })
        self.assertEqual(len(effect), 11)
        self.assertEqual(effect[:4], bytes((0x25, 0x48, 0x00, 4)))

    def test_feedback_effect_activates_zones_from_start(self) -> None:
        effect = bridge.build_trigger_effect({
            "mode": "feedback", "start": 4, "end": 7, "strength": 6,
        })
        self.assertEqual(effect[0], 0x21)
        self.assertEqual(int.from_bytes(effect[1:3], "little"), 0b1111110000)

    def test_report_contains_both_triggers_with_lighting_and_haptics(self) -> None:
        lighting = bridge.normalize_lighting(bridge.CODEX_LIGHT_PROFILES["idle"])
        triggers = bridge.normalize_triggers({
            "left": {"mode": "feedback", "start": 2, "strength": 4},
            "right": {"mode": "weapon", "start": 3, "end": 7, "strength": 8},
        })
        report = bridge.build_lighting_report(
            lighting,
            triggers=triggers,
            haptics_active=True,
            motor_right=20,
            motor_left=10,
        )
        self.assertEqual(len(report), 48)
        self.assertEqual(report[1] & 0x0F, 0x0F)
        self.assertEqual(report[11:15], bytes((0x25, 0x88, 0x00, 7)))
        self.assertEqual(report[22], 0x21)
        self.assertEqual(report[45:48], bytes((230, 237, 236)))

    def test_shutdown_report_releases_triggers_and_motors(self) -> None:
        lighting = bridge.normalize_lighting(bridge.CODEX_LIGHT_PROFILES["working"])
        report = bridge.build_shutdown_report(lighting)

        self.assertEqual(report[1] & 0x0F, 0x0F)
        self.assertEqual((report[3], report[4]), (0, 0))
        self.assertEqual(report[11], bridge.DS5_TRIGGER_EFFECT_OFF)
        self.assertEqual(report[22], bridge.DS5_TRIGGER_EFFECT_OFF)
        self.assertEqual(report[11:22], bytes(11))
        self.assertEqual(report[22:33], bytes(11))

    def test_weapon_range_validation(self) -> None:
        with self.assertRaises(ValueError):
            bridge.normalize_trigger({"mode": "weapon", "start": 1, "end": 5})
        with self.assertRaises(ValueError):
            bridge.normalize_trigger({"mode": "weapon", "start": 7, "end": 9})

    def test_weapon_breakpoint_triggers_one_recoil_until_released(self) -> None:
        engine = bridge.LightEffectEngine()
        engine._triggers = bridge.normalize_triggers({
            "left": {"mode": "off"},
            "right": {"mode": "weapon", "start": 3, "end": 6, "strength": 8},
        })
        engine._haptic_started_at = bridge.time.monotonic()
        overrides = engine.observe_trigger_axes({
            "leftTrigger": 0.0, "rightTrigger": 0.59,
            "leftTriggerEffectStatus": 0, "rightTriggerEffectStatus": 1,
        })
        self.assertFalse(overrides["r2"])
        self.assertIsNone(engine._recoil_started_at)

        overrides = engine.observe_trigger_axes({
            "leftTrigger": 0.0, "rightTrigger": 0.66,
            "leftTriggerEffectStatus": 0, "rightTriggerEffectStatus": 2,
        })
        first_recoil = engine._recoil_started_at
        self.assertIsNotNone(first_recoil)
        self.assertIsNone(engine._haptic_started_at)
        self.assertTrue(overrides["r2"])

        overrides = engine.observe_trigger_axes({
            "leftTrigger": 0.0, "rightTrigger": 0.9,
            "leftTriggerEffectStatus": 0, "rightTriggerEffectStatus": 2,
        })
        self.assertEqual(engine._recoil_started_at, first_recoil)
        self.assertTrue(overrides["r2"])

        overrides = engine.observe_trigger_axes({
            "leftTrigger": 0.0, "rightTrigger": 0.2,
            "leftTriggerEffectStatus": 0, "rightTriggerEffectStatus": 0,
        })
        self.assertFalse(overrides["r2"])
        engine.observe_trigger_axes({
            "leftTrigger": 0.0, "rightTrigger": 0.66,
            "leftTriggerEffectStatus": 0, "rightTriggerEffectStatus": 2,
        })
        self.assertGreaterEqual(engine._recoil_started_at, first_recoil)

    def test_recoil_strength_scales_motor_output(self) -> None:
        engine = bridge.LightEffectEngine()
        engine._triggers = bridge.normalize_triggers({
            "left": {"mode": "off"},
            "right": {"mode": "weapon", "start": 3, "end": 6, "strength": 4},
        })
        engine.observe_trigger_axes({
            "leftTrigger": 0.0, "rightTrigger": 0.7,
            "leftTriggerEffectStatus": 0, "rightTriggerEffectStatus": 2,
        })
        active, motor_right, motor_left = engine._haptic_frame(engine._recoil_started_at)
        self.assertTrue(active)
        self.assertEqual(motor_right, round(bridge.RECOIL_RIGHT_MOTOR / 2))
        self.assertEqual(motor_left, round(bridge.RECOIL_LEFT_MOTOR / 2))

        active, motor_right, motor_left = engine._haptic_frame(
            engine._recoil_started_at + bridge.RECOIL_STRIKE_END_SECONDS + 0.001,
        )
        self.assertTrue(active)
        self.assertEqual((motor_right, motor_left), (0, 0))

    def test_weapon_axis_override_blocks_early_digital_r2_press(self) -> None:
        report = bytearray(64)
        report[0] = 0x01
        report[1:5] = bytes((128, 128, 128, 128))
        report[6] = round(0.4 * 255)
        report[8] = 0x08
        report[9] = 1 << 3

        engine = bridge.InputMappingEngine(lambda _axes: {"r2": False})
        engine._process_report(bytes(report))
        self.assertNotIn("r2", engine.status()["pressed"])

        engine._trigger_observer = lambda _axes: {"r2": True}
        engine._process_report(bytes(report))
        self.assertIn("r2", engine.status()["pressed"])

    def test_usb_input_parses_firmware_trigger_effect_status(self) -> None:
        report = bytearray(64)
        report[0] = 0x01
        report[1:5] = bytes((128, 128, 128, 128))
        report[8] = 0x08
        report[42] = 0x20
        report[43] = 0x10
        _pressed, axes = bridge.parse_dualsense_usb_input(bytes(report))
        self.assertEqual(axes["rightTriggerEffectStatus"], 2)
        self.assertEqual(axes["leftTriggerEffectStatus"], 1)

    def test_lighting_profile_update_preserves_active_recoil(self) -> None:
        engine = bridge.LightEffectEngine()
        engine._thread = self.AliveThread()
        engine._product_id = 0x0CE6
        engine._recoil_started_at = bridge.time.monotonic()
        engine._last_recoil_monotonic_at = engine._recoil_started_at

        result = engine.apply(bridge.CODEX_LIGHT_PROFILES["working"])

        self.assertTrue(result["running"])
        self.assertEqual(result["productId"], 0x0CE6)
        self.assertIsNotNone(engine._recoil_started_at)
        self.assertEqual(engine._config["effect"], "breathe")

    def test_recoil_priority_suppresses_status_transition_pulse(self) -> None:
        engine = bridge.LightEffectEngine()
        engine._thread = self.AliveThread()
        engine._last_recoil_monotonic_at = bridge.time.monotonic()

        self.assertFalse(engine.trigger_double_pulse())
        self.assertIsNone(engine._haptic_started_at)
        self.assertEqual(engine._suppressed_status_pulses, 1)

        engine._last_recoil_monotonic_at -= bridge.RECOIL_PRIORITY_HOLDOFF_SECONDS + 0.01
        self.assertTrue(engine.trigger_double_pulse())
        self.assertIsNotNone(engine._haptic_started_at)


class StickDirectionMappingTests(unittest.TestCase):
    @staticmethod
    def report(
        *,
        left_x: int = 128,
        left_y: int = 128,
        right_x: int = 128,
        right_y: int = 128,
        square: bool = False,
    ) -> bytes:
        report = bytearray(64)
        report[0] = 0x01
        report[1:5] = bytes((left_x, left_y, right_x, right_y))
        report[8] = 0x08 | (0x10 if square else 0)
        report[33] = 0x80
        report[37] = 0x80
        return bytes(report)

    def test_cardinal_direction_uses_hysteresis_until_stick_returns(self) -> None:
        active = bridge.resolve_stick_directions({"leftX": 0.02, "leftY": -0.8})
        self.assertEqual(active, {"left_stick_up"})

        active = bridge.resolve_stick_directions({"leftX": 0.02, "leftY": -0.5}, active)
        self.assertEqual(active, {"left_stick_up"})

        active = bridge.resolve_stick_directions({"leftX": 0.02, "leftY": -0.3}, active)
        self.assertEqual(active, set())

    def test_diagonal_tilt_selects_only_the_dominant_axis(self) -> None:
        active = bridge.resolve_stick_directions({
            "leftX": 0.72,
            "leftY": -0.9,
            "rightX": -0.88,
            "rightY": 0.7,
        })

        self.assertEqual(active, {"left_stick_up", "right_stick_left"})

    def test_left_stick_up_dispatches_codex_previous_chat_once(self) -> None:
        engine = bridge.InputMappingEngine()
        engine.configure({
            "enabled": True,
            "mappings": {"left_stick_up": ["ControlLeft", "PageUp"]},
        })

        with patch.object(bridge, "send_keyboard_codes") as send:
            engine._process_report(self.report(left_y=28))
            engine._process_report(self.report(left_y=42))
            engine._process_report(self.report())

        self.assertEqual(send.call_count, 2)
        self.assertEqual(send.call_args_list[0].args, (["ControlLeft", "PageUp"], False))
        self.assertEqual(send.call_args_list[1].args, (["PageUp", "ControlLeft"], True))
        status = engine.status()
        self.assertEqual(status["dispatchCount"], 1)
        self.assertEqual(status["lastDispatchedButton"], "left_stick_up")

    def test_capture_suspension_blocks_controller_shortcut_dispatch(self) -> None:
        engine = bridge.InputMappingEngine()
        engine.configure({
            "enabled": True,
            "mappings": {"left_stick_up": ["ControlLeft", "PageUp"]},
        })
        engine.set_capture_suspended(True)

        with patch.object(bridge, "send_keyboard_codes") as send:
            engine._process_report(self.report(left_y=28))

        send.assert_not_called()
        self.assertTrue(engine.status()["captureSuspended"])

    def test_right_stick_uses_repeating_mouse_wheel_until_released(self) -> None:
        engine = bridge.InputMappingEngine()
        engine.configure({
            "enabled": True,
            "mappings": {"right_stick_down": ["MouseWheelDown"]},
        })

        with patch.object(bridge, "send_mouse_wheel") as wheel:
            engine._process_report(self.report(right_y=250))
            wheel.assert_called_once_with(-bridge.WHEEL_DELTA)
            engine._repeat_action_next["right_stick_down"] = 0
            engine._process_report(self.report(right_y=250))
            self.assertEqual(wheel.call_count, 2)
            engine._process_report(self.report())

        self.assertNotIn("right_stick_down", engine._repeat_action_next)
        self.assertEqual(engine.status()["dispatchCount"], 2)

    def test_smart_delete_short_press_sends_one_backspace(self) -> None:
        engine = bridge.InputMappingEngine()
        engine.configure({
            "enabled": True,
            "mappings": {"square": ["CodexSmartDelete"]},
        })

        with patch.object(bridge, "send_keyboard_codes") as send:
            engine._process_report(self.report(square=True))
            send.assert_not_called()
            engine._process_report(self.report())

        self.assertEqual(send.call_args_list[0].args, (["Backspace"], False))
        self.assertEqual(send.call_args_list[1].args, (["Backspace"], True))
        status = engine.status()
        self.assertEqual(status["lastDispatchedButton"], "square")
        self.assertEqual(status["lastShortcut"], ["Backspace"])

    def test_smart_delete_long_press_clears_input_without_extra_backspace(self) -> None:
        engine = bridge.InputMappingEngine()
        engine.configure({
            "enabled": True,
            "mappings": {"square": ["CodexSmartDelete"]},
        })

        with patch.object(bridge, "send_keyboard_codes") as send:
            engine._process_report(self.report(square=True))
            engine._smart_delete_started["square"] -= bridge.SMART_DELETE_HOLD_SECONDS + 0.01
            engine._process_report(self.report(square=True))
            self.assertEqual(send.call_count, 4)
            engine._process_report(self.report())

        self.assertEqual(send.call_count, 4)
        self.assertEqual(send.call_args_list[0].args, (["ControlLeft", "KeyA"], False))
        self.assertEqual(send.call_args_list[1].args, (["KeyA", "ControlLeft"], True))
        self.assertEqual(send.call_args_list[2].args, (["Backspace"], False))
        self.assertEqual(send.call_args_list[3].args, (["Backspace"], True))
        status = engine.status()
        self.assertEqual(status["lastDispatchedButton"], "square")
        self.assertEqual(status["lastShortcut"], ["CodexClearInput"])


class KeyboardCaptureEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.suspension_changes: list[bool] = []
        self.engine = bridge.KeyboardCaptureEngine(self.suspension_changes.append)
        self.engine._hook = 1

    def tearDown(self) -> None:
        self.engine.cancel()

    def test_combination_is_swallowed_and_normalized_before_delivery(self) -> None:
        self.engine.begin()

        self.assertTrue(self.engine.process_event("ShiftLeft", True))
        self.assertTrue(self.engine.process_event("ControlLeft", True))
        self.assertTrue(self.engine.process_event("BracketLeft", True))
        self.assertTrue(self.engine.status()["ready"])
        self.assertTrue(self.engine.status()["blocking"])

        self.engine.process_event("BracketLeft", False)
        self.engine.process_event("ControlLeft", False)
        self.engine.process_event("ShiftLeft", False)
        result = self.engine.consume()

        self.assertEqual(result["result"], ["ControlLeft", "ShiftLeft", "BracketLeft"])
        self.assertFalse(result["blocking"])
        self.assertEqual(self.suspension_changes[:2], [True, False])

    def test_modifier_only_capture_completes_when_modifier_is_released(self) -> None:
        self.engine.begin()
        self.engine.process_event("ControlLeft", True)
        self.engine.process_event("ControlLeft", False)

        self.assertEqual(self.engine.consume()["result"], ["ControlLeft"])

    def test_injected_input_is_blocked_but_not_recorded(self) -> None:
        self.engine.begin()

        self.assertTrue(self.engine.process_event("KeyA", True, injected=True))
        self.assertEqual(self.engine.status()["codes"], [])
        self.assertFalse(self.engine.status()["ready"])


class TouchpadGestureTests(unittest.TestCase):
    @staticmethod
    def report(
        *,
        pressed: bool = False,
        touch: tuple[int, int, int] | None = None,
    ) -> bytes:
        report = bytearray(64)
        report[0] = 0x01
        report[1:5] = bytes((128, 128, 128, 128))
        report[8] = 0x08
        report[10] = (1 << 1) if pressed else 0
        report[33] = 0x80
        report[37] = 0x80
        if touch is not None:
            touch_id, x, y = touch
            report[33] = touch_id & 0x7F
            report[34] = x & 0xFF
            report[35] = ((x >> 8) & 0x0F) | ((y & 0x0F) << 4)
            report[36] = (y >> 4) & 0xFF
        return bytes(report)

    def configured_engine(self) -> bridge.InputMappingEngine:
        engine = bridge.InputMappingEngine()
        engine.configure({
            "enabled": True,
            "mappings": {"touchpad": ["Tab"]},
            "touchpadGestures": {"enabled": True, "threshold": 320},
        })
        return engine

    def test_usb_input_parses_first_active_touch_point(self) -> None:
        pressed, axes = bridge.parse_dualsense_usb_input(
            self.report(pressed=True, touch=(7, 1510, 731))
        )

        self.assertIn("touchpad", pressed)
        self.assertTrue(axes["touchActive"])
        self.assertEqual(axes["touchId"], 7)
        self.assertEqual((axes["touchX"], axes["touchY"]), (1510, 731))

    def test_swipe_does_not_require_physical_touchpad_press(self) -> None:
        engine = bridge.InputMappingEngine(touchpad_swipe_handler=lambda _direction: "touch-injection")
        engine.configure({
            "enabled": True,
            "mappings": {"touchpad": ["Tab"]},
            "touchpadGestures": {"enabled": True, "threshold": 320},
        })
        with patch.object(bridge, "send_keyboard_codes") as send:
            engine._process_report(self.report(touch=(1, 300, 500)))
            engine._process_report(self.report(touch=(1, 900, 500)))

        send.assert_not_called()
        self.assertEqual(engine.status()["dispatchCount"], 1)

    def test_touchpad_click_dispatches_mapping_when_gestures_are_enabled(self) -> None:
        engine = self.configured_engine()
        with patch.object(bridge, "send_keyboard_codes") as send:
            engine._process_report(self.report(pressed=True, touch=(3, 900, 500)))
            send.assert_not_called()
            engine._process_report(self.report())

        self.assertEqual(send.call_count, 2)
        send.assert_any_call(["Tab"], False)
        send.assert_any_call(["Tab"], True)
        status = engine.status()
        self.assertEqual(status["dispatchCount"], 1)
        self.assertEqual(status["lastDispatchedButton"], "touchpad")
        self.assertEqual(status["lastShortcut"], ["Tab"])

    def test_touchpad_dictation_focuses_codex_before_native_shortcut(self) -> None:
        engine = bridge.InputMappingEngine()
        engine.configure({
            "enabled": True,
            "mappings": {"touchpad": ["CodexDictation"]},
            "touchpadGestures": {"enabled": False, "threshold": 320},
        })
        with patch.object(bridge, "focus_or_launch_codex") as focus, \
                patch.object(bridge.time, "sleep") as sleep, \
                patch.object(bridge, "send_keyboard_codes") as send:
            engine._process_report(self.report(pressed=True, touch=(3, 900, 500)))
            focus.assert_called_once_with()
            sleep.assert_called_once_with(bridge.CODEX_FOCUS_SHORTCUT_DELAY_SECONDS)
            self.assertEqual(send.call_args_list[0].args, (["ControlLeft", "ShiftLeft", "KeyD"], False))
            engine._process_report(self.report())

        self.assertEqual(send.call_args_list[1].args, (["KeyD", "ShiftLeft", "ControlLeft"], True))
        status = engine.status()
        self.assertEqual(status["lastDispatchedButton"], "touchpad")
        self.assertEqual(status["lastShortcut"], ["CodexDictation"])

    def test_four_finger_touch_injection_bypasses_keyboard_fallback(self) -> None:
        engine = bridge.InputMappingEngine(touchpad_swipe_handler=lambda _direction: "touch-injection")
        engine.configure({
            "enabled": True,
            "mappings": {},
            "touchpadGestures": {"enabled": True, "threshold": 320},
        })
        with patch.object(bridge, "send_keyboard_codes") as send:
            engine._process_report(self.report(touch=(6, 300, 500)))
            engine._process_report(self.report(touch=(6, 700, 500)))

        send.assert_not_called()
        status = engine.status()
        self.assertEqual(status["dispatchCount"], 1)
        self.assertEqual(status["touchpadGestures"]["switchMode"], "touch-injection")

    def test_native_touchpad_backend_requires_virtual_hid_driver(self) -> None:
        with patch.object(
            bridge,
            "send_virtual_touchpad_swipe",
            side_effect=FileNotFoundError,
        ) as send:
            mode = bridge.perform_touchpad_swipe("left")

        send.assert_called_once_with("left")
        self.assertEqual(mode, "driver-required")

    def test_native_touchpad_backend_uses_virtual_hid(self) -> None:
        with patch.object(bridge, "send_virtual_touchpad_swipe") as send:
            mode = bridge.perform_touchpad_swipe("right")

        send.assert_called_once_with("right")
        self.assertEqual(mode, "touch-injection")

    def test_virtual_touchpad_report_has_four_active_contacts_in_five_slots(self) -> None:
        report = bridge.build_virtual_touchpad_report([
            (100, 200, True),
            (300, 400, True),
            (500, 600, True),
            (700, 800, True),
        ], 0x1234)

        self.assertEqual(len(report), bridge.VIRTUAL_TOUCHPAD_REPORT_LENGTH)
        self.assertEqual(report[0], bridge.VIRTUAL_TOUCHPAD_REPORT_ID)
        self.assertEqual([report[index] for index in (1, 10, 19, 28)], [0x03] * 4)
        self.assertEqual([
            int.from_bytes(report[index:index + 4], "little")
            for index in (2, 11, 20, 29)
        ], [0, 1, 2, 3])
        self.assertEqual(report[37:46], bytes(9))
        self.assertEqual(report[-4:], b"\x34\x12\x04\x00")

    def test_virtual_touchpad_swipe_uses_short_continuous_track(self) -> None:
        reports = []
        with patch.object(bridge, "find_virtual_touchpad", return_value=("test-path", 123)), \
                patch.object(bridge, "write_report", side_effect=lambda _handle, report: reports.append(bytes(report))), \
                patch.object(bridge.time, "sleep") as sleep, \
                patch.object(bridge.kernel32, "CloseHandle"):
            bridge.send_virtual_touchpad_swipe("right")

        self.assertEqual(len(reports), bridge.VIRTUAL_TOUCHPAD_MOVE_STEPS + 3)
        self.assertEqual(sleep.call_count, bridge.VIRTUAL_TOUCHPAD_MOVE_STEPS + 2)
        self.assertLess(
            sleep.call_count * bridge.VIRTUAL_TOUCHPAD_FRAME_SECONDS,
            0.1,
        )
        self.assertEqual([report[-2] for report in reports[:-1]], [4] * (len(reports) - 1))
        self.assertEqual([reports[-2][index] for index in (1, 10, 19, 28)], [0x01] * 4)
        self.assertEqual(reports[-1][-2], 0)
        contact_x = [int.from_bytes(report[6:8], "little") for report in reports]
        self.assertEqual(contact_x, sorted(contact_x))

    def test_driver_required_does_not_inject_keyboard_or_touchscreen(self) -> None:
        engine = bridge.InputMappingEngine(touchpad_swipe_handler=lambda _direction: "driver-required")
        engine.configure({
            "enabled": True,
            "mappings": {},
            "touchpadGestures": {"enabled": True, "threshold": 320},
        })
        with patch.object(bridge, "send_keyboard_codes") as send:
            engine._process_report(self.report(touch=(7, 300, 500)))
            engine._process_report(self.report(touch=(7, 700, 500)))

        send.assert_not_called()
        status = engine.status()["touchpadGestures"]
        self.assertEqual(status["switchMode"], "driver-required")
        self.assertIn("virtual HID touchpad driver", status["switchError"])

    def test_unavailable_touch_injection_does_not_fall_back_to_keyboard(self) -> None:
        engine = bridge.InputMappingEngine(touchpad_swipe_handler=lambda _direction: "unavailable")
        engine.configure({
            "enabled": True,
            "mappings": {},
            "touchpadGestures": {"enabled": True, "threshold": 320},
        })
        with patch.object(bridge, "send_keyboard_codes") as send:
            engine._process_report(self.report(touch=(7, 300, 500)))
            engine._process_report(self.report(touch=(7, 700, 500)))

        send.assert_not_called()
        status = engine.status()["touchpadGestures"]
        self.assertEqual(status["switchMode"], "unavailable")
        self.assertIn("keyboard fallback disabled", status["switchError"])

    def test_right_swipe_dispatches_once_and_suppresses_touchpad_mapping(self) -> None:
        engine = bridge.InputMappingEngine(touchpad_swipe_handler=lambda _direction: "touch-injection")
        engine.configure({
            "enabled": True,
            "mappings": {"touchpad": ["Tab"]},
            "touchpadGestures": {"enabled": True, "threshold": 320},
        })
        with patch.object(bridge, "send_keyboard_codes") as send:
            engine._process_report(self.report(pressed=True, touch=(2, 300, 500)))
            self.assertIn("touchpad", engine.status()["pressed"])
            engine._process_report(self.report(pressed=True, touch=(2, 700, 510)))
            engine._process_report(self.report(pressed=True, touch=(2, 1100, 510)))

        send.assert_not_called()
        status = engine.status()
        self.assertEqual(status["dispatchCount"], 1)
        self.assertEqual(status["lastDispatchedButton"], "touchpad_swipe_right")
        self.assertEqual(status["touchpadGestures"]["lastGesture"], "right")

    def test_swipe_can_toggle_system_mute_after_desktop_switch(self) -> None:
        engine = bridge.InputMappingEngine(touchpad_swipe_handler=lambda _direction: "touch-injection")
        engine.configure({
            "enabled": True,
            "mappings": {},
            "touchpadGestures": {"enabled": True, "threshold": 320, "muteOnSwitch": True},
        })
        with patch.object(bridge, "send_keyboard_codes") as send:
            engine._process_report(self.report(pressed=True, touch=(5, 300, 500)))
            engine._process_report(self.report(pressed=True, touch=(5, 700, 500)))

        self.assertEqual(send.call_count, 2)
        self.assertEqual(send.call_args_list[0].args, (["VolumeMute"], False))
        self.assertEqual(send.call_args_list[1].args, (["VolumeMute"], True))
        status = engine.status()["touchpadGestures"]
        self.assertEqual(status["muteCount"], 1)
        self.assertIsNotNone(status["lastMuteAt"])

    def test_mute_on_switch_defaults_to_off(self) -> None:
        config = bridge.normalize_touchpad_gestures({"enabled": True, "threshold": 320})
        self.assertFalse(config["muteOnSwitch"])

    def test_volume_mute_uses_extended_scan_code_instead_of_letter_d(self) -> None:
        event = bridge.keyboard_event("VolumeMute", False)

        self.assertEqual(event.ki.wScan, 0x20)
        self.assertTrue(event.ki.dwFlags & bridge.KEYEVENTF_SCANCODE)
        self.assertTrue(event.ki.dwFlags & bridge.KEYEVENTF_EXTENDEDKEY)

    def test_release_rearms_gesture_for_next_left_swipe(self) -> None:
        engine = bridge.InputMappingEngine(touchpad_swipe_handler=lambda _direction: "touch-injection")
        engine.configure({
            "enabled": True,
            "mappings": {"touchpad": ["Tab"]},
            "touchpadGestures": {"enabled": True, "threshold": 320},
        })
        with patch.object(bridge, "send_keyboard_codes") as send:
            engine._process_report(self.report(pressed=True, touch=(3, 300, 500)))
            engine._process_report(self.report(pressed=True, touch=(3, 700, 500)))
            engine._process_report(self.report())
            engine._process_report(self.report(pressed=True, touch=(4, 1000, 500)))
            engine._process_report(self.report(pressed=True, touch=(4, 600, 500)))

        send.assert_not_called()
        status = engine.status()
        self.assertEqual(status["dispatchCount"], 2)
        self.assertEqual(status["lastDispatchedButton"], "touchpad_swipe_left")
        self.assertEqual(status["lastShortcut"], ["MetaLeft", "ControlLeft", "ArrowLeft"])

    def test_gesture_threshold_validation(self) -> None:
        with self.assertRaises(ValueError):
            bridge.normalize_touchpad_gestures({"enabled": True, "threshold": 80})

if __name__ == "__main__":
    unittest.main()
