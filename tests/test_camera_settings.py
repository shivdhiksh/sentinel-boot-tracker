"""
Unit and Integration tests for Sentinel Remote Camera Opt-In, Automatic Capture, and Security.
Labels: UNIT / SIMULATED / INTEGRATION / STATIC/INSPECTION
"""
import os
import json
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from sentinel.settings import (
    SETTINGS_FILE,
    is_remote_camera_enabled,
    set_remote_camera_enabled,
    get_camera_settings_summary
)
from sentinel.remote_actions import execute_camera, _camera_lock
from sentinel.command_engine import CommandEngine, ALLOWLIST
from sentinel.consent_camera import CameraConsentDialog, CameraCaptureIndicator, _create_mock_image


# =====================================================================
# 1. SETTINGS & PERSISTENCE TESTS
# =====================================================================

def test_camera_disabled_by_default(tmp_path):
    """[UNIT] Verifies Remote Camera is disabled by default when settings file is absent."""
    test_settings = tmp_path / ".test_settings.json"
    with patch("sentinel.settings.SETTINGS_FILE", test_settings):
        assert is_remote_camera_enabled() is False


def test_owner_enable_and_disable_setting(tmp_path):
    """[UNIT] Verifies owner can enable, persist, and disable the persistent opt-in setting."""
    test_settings = tmp_path / ".test_settings.json"
    with patch("sentinel.settings.SETTINGS_FILE", test_settings):
        assert is_remote_camera_enabled() is False

        # Enable
        ok_en = set_remote_camera_enabled(True)
        assert ok_en is True
        assert is_remote_camera_enabled() is True
        assert test_settings.exists()

        summary = get_camera_settings_summary()
        assert summary["remote_camera_enabled"] is True
        assert summary["updated_at"] != "Never"

        # Disable
        ok_dis = set_remote_camera_enabled(False)
        assert ok_dis is True
        assert is_remote_camera_enabled() is False

        summary2 = get_camera_settings_summary()
        assert summary2["remote_camera_enabled"] is False


def test_corrupt_settings_file_defaults_to_disabled(tmp_path):
    """[UNIT] Verifies corrupt or invalid JSON safely defaults to disabled."""
    test_settings = tmp_path / ".test_settings.json"
    with patch("sentinel.settings.SETTINGS_FILE", test_settings):
        # Write corrupted JSON
        test_settings.write_text("{malformed: true, invalid...", encoding="utf-8")
        assert is_remote_camera_enabled() is False

        # Write non-dict JSON (e.g. array or integer)
        test_settings.write_text("[1, 2, 3]", encoding="utf-8")
        assert is_remote_camera_enabled() is False


def test_settings_excludes_secrets_and_tokens(tmp_path):
    """[UNIT / STATIC] Verifies .settings.json strictly stores preferences, no tokens or secrets."""
    test_settings = tmp_path / ".test_settings.json"
    with patch("sentinel.settings.SETTINGS_FILE", test_settings):
        set_remote_camera_enabled(True)
        content = test_settings.read_text(encoding="utf-8")
        data = json.loads(content)

        # Check keys
        assert "remote_camera_enabled" in data
        assert "updated_at" in data
        assert len(data) == 2  # Only preference and timestamp

        # Verify no token or secret keys exist
        for key in ["token", "secret", "password", "bot_token", "chat_id"]:
            assert key not in data
            assert key not in content.lower()


# =====================================================================
# 2. REMOTE ACTIONS: EXECUTE_CAMERA TESTS
# =====================================================================

def test_execute_camera_rejected_when_disabled():
    """[UNIT] Verifies execute_camera safely rejects requests when feature is disabled."""
    with patch("sentinel.remote_actions.is_remote_camera_enabled", return_value=False):
        temp_path, msg = execute_camera()
        assert temp_path is None
        assert "Remote Camera is disabled" in msg
        assert "py power_monitor.py camera-enable" in msg


def test_execute_camera_rejected_in_session_0():
    """[UNIT] Verifies execute_camera rejects execution in Session 0 or non-interactive sessions."""
    with patch("sentinel.remote_actions.is_remote_camera_enabled", return_value=True), \
         patch("sentinel.remote_actions.verify_interactive_session", return_value=(False, "Session 0 non-interactive")):
        temp_path, msg = execute_camera()
        assert temp_path is None
        assert "Camera rejected" in msg
        assert "Session 0" in msg


def test_execute_camera_concurrent_protection():
    """[UNIT] Verifies concurrent requests are prevented from opening the camera simultaneously."""
    with patch("sentinel.remote_actions._camera_in_progress", True):
        temp_path, msg = execute_camera()
        assert temp_path is None
        assert "Camera capture already in progress" in msg


def test_execute_camera_auto_mock_success(tmp_path):
    """[UNIT / SIMULATED] Verifies successful auto capture with mock test mode and cleanup."""
    set_remote_camera_enabled(True)
    try:
        with patch("sentinel.remote_actions.verify_interactive_session", return_value=(True, "")):
            temp_path, caption = execute_camera(test_mode="mock_capture")
            assert temp_path is not None
            assert os.path.exists(temp_path)
            assert os.path.getsize(temp_path) > 0
            assert "Camera Snapshot" in caption
            assert "Remote Authorized Capture" in caption

            # Cleanup test file
            try:
                os.remove(temp_path)
            except Exception:
                pass
    finally:
        set_remote_camera_enabled(False)


def test_execute_camera_device_unavailable():
    """[UNIT / SIMULATED] Verifies camera hardware error handling when device is unavailable."""
    with patch("sentinel.remote_actions.is_remote_camera_enabled", return_value=True), \
         patch("sentinel.remote_actions.verify_interactive_session", return_value=(True, "")):

        temp_path, msg = execute_camera(test_mode="unavailable")
        assert temp_path is None
        assert "Camera hardware/driver error" in msg or "No camera hardware detected" in msg


def test_execute_camera_subprocess_timeout_cleanup():
    """[UNIT / SIMULATED] Verifies timeout in camera subprocess cleans up temp file."""
    import subprocess
    temp_dir = tempfile.gettempdir()
    before_files = set(os.listdir(temp_dir))

    with patch("sentinel.remote_actions.is_remote_camera_enabled", return_value=True), \
         patch("sentinel.remote_actions.verify_interactive_session", return_value=(True, "")), \
         patch("sentinel.remote_actions.subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 25)):

        temp_path, msg = execute_camera()
        assert temp_path is None
        assert "Camera request timed out" in msg

        after_files = set(os.listdir(temp_dir))
        new_cam_files = [f for f in (after_files - before_files) if f.startswith("sentinel_cam_")]
        assert len(new_cam_files) == 0


# =====================================================================
# 3. COMMAND ENGINE DISPATCH, AUDIT & TELEGRAM TESTS
# =====================================================================

def test_command_engine_camera_when_disabled(tmp_path):
    """[INTEGRATION] Verifies Telegram /camera when disabled returns guidance and audits REJECTED."""
    test_state = tmp_path / ".test_update_state.json"
    with patch("sentinel.command_engine.STATE_FILE", test_state), \
         patch("sentinel.command_engine.is_authorized", return_value=True), \
         patch("sentinel.command_engine.send_telegram_message") as mock_send, \
         patch("sentinel.command_engine.log_command_audit") as mock_audit, \
         patch("sentinel.remote_actions.is_remote_camera_enabled", return_value=False):

        engine = CommandEngine()
        update = {
            "update_id": 4001,
            "message": {
                "chat": {"id": 123456789},
                "text": "/camera"
            }
        }
        engine.process_update(update)

        assert mock_send.called
        sent_text = mock_send.call_args[0][0]
        assert "Remote Camera is disabled" in sent_text
        assert "camera-enable" in sent_text

        # Audit should record REJECTED
        assert mock_audit.called
        audit_call = mock_audit.call_args[1]
        assert audit_call.get("result") == "REJECTED"


def test_command_engine_camera_unauthorized(tmp_path):
    """[UNIT] Verifies unauthorized Telegram chat cannot trigger camera capture."""
    test_state = tmp_path / ".test_update_state.json"
    with patch("sentinel.command_engine.STATE_FILE", test_state), \
         patch("sentinel.command_engine.is_authorized", return_value=False), \
         patch("sentinel.command_engine.send_telegram_message") as mock_send, \
         patch("sentinel.command_engine.execute_camera") as mock_exec_cam:

        engine = CommandEngine()
        update = {
            "update_id": 4002,
            "message": {
                "chat": {"id": 999999999},
                "text": "/camera"
            }
        }
        engine.process_update(update)

        assert mock_exec_cam.called is False
        assert mock_send.called is True
        assert "Access Denied" in mock_send.call_args[0][0]


def test_command_engine_camera_success_and_cleanup(tmp_path):
    """[INTEGRATION] Verifies authorized /camera captures, sends photo, cleans up, and audits SUCCESS."""
    test_state = tmp_path / ".test_update_state.json"
    fake_img = tmp_path / "mock_cam_snap.jpg"
    fake_img.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 100)

    with patch("sentinel.command_engine.STATE_FILE", test_state), \
         patch("sentinel.command_engine.is_authorized", return_value=True), \
         patch("sentinel.command_engine.execute_camera", return_value=(str(fake_img), "📷 Camera Snapshot")), \
         patch("sentinel.command_engine.send_telegram_photo", return_value=True) as mock_photo, \
         patch("sentinel.command_engine.log_command_audit") as mock_audit:

        engine = CommandEngine()
        update = {
            "update_id": 4003,
            "message": {
                "chat": {"id": 123456789},
                "text": "/camera"
            }
        }
        engine.process_update(update)

        assert mock_photo.called
        # Verify temporary file cleaned up after upload
        assert not fake_img.exists()

        # Verify audit log
        assert mock_audit.called
        audit_call = mock_audit.call_args[1]
        assert audit_call.get("result") == "SUCCESS"


def test_command_engine_camera_upload_failure_cleanup(tmp_path):
    """[INTEGRATION] Verifies temp image is cleaned up even if Telegram photo upload fails."""
    test_state = tmp_path / ".test_update_state.json"
    fake_img = tmp_path / "mock_cam_snap_fail.jpg"
    fake_img.write_bytes(b"\xFF\xD8\xFF\xE0" + b"\x00" * 100)

    with patch("sentinel.command_engine.STATE_FILE", test_state), \
         patch("sentinel.command_engine.is_authorized", return_value=True), \
         patch("sentinel.command_engine.execute_camera", return_value=(str(fake_img), "📷 Camera Snapshot")), \
         patch("sentinel.command_engine.send_telegram_photo", return_value=False) as mock_photo, \
         patch("sentinel.command_engine.send_telegram_message") as mock_msg, \
         patch("sentinel.command_engine.log_command_audit") as mock_audit:

        engine = CommandEngine()
        update = {
            "update_id": 4004,
            "message": {
                "chat": {"id": 123456789},
                "text": "/camera"
            }
        }
        engine.process_update(update)

        assert mock_photo.called
        assert mock_msg.called
        assert "Failed to transmit photo" in mock_msg.call_args[0][0]
        # Verify file cleaned up on upload failure
        assert not fake_img.exists()
        # Verify audit log recorded FAILED
        assert mock_audit.called
        audit_call = mock_audit.call_args[1]
        assert audit_call.get("result") == "FAILED"


# =====================================================================
# 4. SECURITY BOUNDARIES & NO REMOTE ENABLING
# =====================================================================

def test_no_remote_enable_camera_in_allowlist():
    """[STATIC/INSPECTION] Verifies Telegram ALLOWLIST contains no commands to enable Remote Camera."""
    disallowed = ["/camera_enable", "/enable_camera", "/camera-enable", "/camera_on"]
    for cmd in disallowed:
        assert cmd not in ALLOWLIST, f"Security violation: {cmd} must not be in remote ALLOWLIST"


def test_auto_capture_skips_dialog(tmp_path):
    """
    [UNIT] Verifies that when auto mode is used, CameraConsentDialog is never shown
    and execution skips the dialog.
    """
    out_file = tmp_path / "test_auto.jpg"
    with patch("sys.argv", ["consent_camera.py", str(out_file), "--auto", "--test-mode", "mock_capture"]), \
         patch("sentinel.consent_camera.CameraConsentDialog") as mock_dialog, \
         patch("sentinel.consent_camera.is_remote_camera_enabled", return_value=True), \
         patch("sentinel.consent_camera.verify_interactive_session", return_value=(True, "")):

        with pytest.raises(SystemExit) as exc_info:
            from sentinel.consent_camera import main
            main()
        assert exc_info.value.code == 0
        # In auto mode, CameraConsentDialog should NEVER be instantiated
        assert mock_dialog.called is False
