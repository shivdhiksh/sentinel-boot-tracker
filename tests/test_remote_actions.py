"""
Functional, Unit, and Real E2E tests for sentinel.remote_actions.
Labels: REAL E2E / UNIT
"""
import os
import time
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from sentinel.remote_actions import (
    execute_status,
    execute_location,
    execute_lock,
    execute_shutdown_request,
    execute_confirm_shutdown,
    execute_screenshot,
    execute_processes,
    execute_camera
)

@pytest.fixture(autouse=True)
def prevent_real_shutdown(monkeypatch):
    """
    SAFETY INTERCEPTOR:
    Hard-blocks any call to shutdown.exe across all tests in this file.
    If any code path attempts to invoke the Windows shutdown binary,
    it raises a RuntimeError instead of powering off the machine.
    """
    import subprocess
    orig_popen = subprocess.Popen

    def safe_popen(*args, **kwargs):
        cmd = args[0] if args else kwargs.get("args", [])
        if isinstance(cmd, (list, tuple)):
            cmd_str = " ".join(str(x) for x in cmd).lower()
        else:
            cmd_str = str(cmd).lower()
        if "shutdown" in cmd_str:
            raise RuntimeError(f"SAFETY VIOLATION: Execution of shutdown executable blocked during pytest: {cmd}")
        return orig_popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", safe_popen)
    monkeypatch.setattr("sentinel.remote_actions.subprocess.Popen", safe_popen)

def test_execute_status():
    """[REAL E2E] Verifies status report on live hardware."""
    res = execute_status()
    assert "SENTINEL STATUS — ONLINE" in res
    assert "Hostname:" in res
    assert "OS:" in res
    assert "CPU Load:" in res
    assert "RAM Usage:" in res
    assert "Battery:" in res
    assert "Public IP:" in res
    assert "Sentinel Version:" in res

def test_execute_location():
    """[REAL E2E] Verifies multi-tier location resolution."""
    res = execute_location()
    assert "SENTINEL LOCATION REPORT" in res
    assert "Tier:" in res
    assert "Source:" in res
    if "IP Geolocation Fallback" in res:
        assert "IP-based location is not precise" in res

def test_execute_lock_unit():
    """[UNIT] Verifies workstation lock API invocation (mocked)."""
    with patch("ctypes.windll.user32.LockWorkStation", return_value=1):
        res = execute_lock()
        assert res == "✅ Workstation locked"

def test_shutdown_confirmation_state_machine():
    """
    [UNIT] Verifies two-step confirmation, 30s monotonic expiration, and chat binding.
    GUARANTEE: Real shutdown.exe can NEVER execute. The deferred background thread
    is mocked at the threading.Thread level and executed safely in-test.
    """
    chat_a = "123456789"
    chat_b = "987654321"

    # Step 1: Initial shutdown request
    prompt = execute_shutdown_request(chat_a)
    assert "Confirm shutdown" in prompt
    assert "/confirm_shutdown" in prompt

    # Step 2: Confirmation from mismatched chat ID is rejected
    ok_b, msg_b = execute_confirm_shutdown(chat_b)
    assert ok_b is False
    assert "chat ID mismatch" in msg_b

    # Step 3: Expired confirmation (>30s) is rejected
    with patch("time.monotonic", return_value=time.monotonic() + 35.0):
        ok_exp, msg_exp = execute_confirm_shutdown(chat_a)
        assert ok_exp is False
        assert "expired" in msg_exp

    # Step 4: Valid confirmation within 30s accepted
    execute_shutdown_request(chat_a)

    mock_thread_instance = MagicMock()
    with patch("sentinel.remote_actions.threading.Thread", return_value=mock_thread_instance) as mock_thread_cls, \
         patch("sentinel.remote_actions.subprocess.Popen") as mock_popen, \
         patch("sentinel.remote_actions.time.sleep") as mock_sleep:

        ok_valid, msg_valid = execute_confirm_shutdown(chat_a)
        assert ok_valid is True
        assert "Shutdown command accepted" in msg_valid

        # Assert thread creation and start (no real OS thread spawned)
        assert mock_thread_cls.called
        assert mock_thread_instance.start.called
        assert mock_thread_cls.call_args[1].get("daemon") is True

        # Extract deferred target function and safely execute it synchronously
        deferred_target = mock_thread_cls.call_args[1].get("target")
        assert deferred_target is not None
        deferred_target()

        # Verify time.sleep and exact shutdown command arguments
        mock_sleep.assert_called_once_with(1.5)
        mock_popen.assert_called_once()
        cmd_args = mock_popen.call_args[0][0]
        assert cmd_args[0] == "shutdown.exe"
        assert "/s" in cmd_args
        assert "/t" in cmd_args
        assert "5" in cmd_args
        assert "Sentinel remote shutdown initiated" in cmd_args

def test_execute_camera_deny():
    """[REAL E2E / SIMULATED] Verifies camera denial flow and temp file cleanup."""
    temp_dir = tempfile.gettempdir()
    before_files = set(os.listdir(temp_dir))

    temp_path, msg = execute_camera(test_mode="deny")
    assert temp_path is None
    assert "Local user clicked Deny" in msg

    # Verify no leaked sentinel camera temp files remain
    after_files = set(os.listdir(temp_dir))
    new_cam_files = [f for f in (after_files - before_files) if f.startswith("sentinel_cam_")]
    assert len(new_cam_files) == 0, f"Leaked temporary camera files found: {new_cam_files}"

def test_execute_camera_timeout():
    """[REAL E2E / SIMULATED] Verifies camera timeout flow and temp file cleanup."""
    temp_dir = tempfile.gettempdir()
    before_files = set(os.listdir(temp_dir))

    temp_path, msg = execute_camera(test_mode="timeout")
    assert temp_path is None
    assert "timed out without local user consent" in msg

    # Verify no leaked sentinel camera temp files remain
    after_files = set(os.listdir(temp_dir))
    new_cam_files = [f for f in (after_files - before_files) if f.startswith("sentinel_cam_")]
    assert len(new_cam_files) == 0, f"Leaked temporary camera files found: {new_cam_files}"

def test_execute_processes_real_e2e():
    """[REAL E2E] Verifies process summary collects PID/Name/RAM/CPU and excludes cmdline."""
    output = execute_processes()
    assert "ACTIVE PROCESSES" in output
    assert "PID" in output
    assert "NAME" in output
    assert "RAM" in output
    assert "CPU" in output
    assert "Command line arguments omitted for security" in output

def test_execute_screenshot_manual():
    """
    [MANUAL / REAL E2E - REQUIRES MANUAL APPROVAL]
    Verifies desktop screenshot capture and cleanup on live display.
    """
    if os.getenv("SENTINEL_RUN_MANUAL_TESTS") != "1":
        pytest.skip("Screenshot test requires manual approval (set SENTINEL_RUN_MANUAL_TESTS=1)")

    temp_path, caption = execute_screenshot()
    assert temp_path is not None, f"Screenshot capture failed: {caption}"
    assert os.path.exists(temp_path)
    assert os.path.getsize(temp_path) > 1000  # Non-empty PNG
    assert "Desktop Screenshot" in caption

    # Clean up
    try:
        os.remove(temp_path)
    except Exception:
        pass
    assert not os.path.exists(temp_path)

def test_execute_camera_approve_manual():
    """
    [MANUAL / REAL E2E - REQUIRES MANUAL APPROVAL]
    Verifies camera hardware capture on live webcam with visible consent banner.
    """
    if os.getenv("SENTINEL_RUN_MANUAL_TESTS") != "1":
        pytest.skip("Camera hardware capture requires manual approval (set SENTINEL_RUN_MANUAL_TESTS=1)")

    temp_path, caption = execute_camera(test_mode="approve")
    assert temp_path is not None, f"Camera capture failed: {caption}"
    assert os.path.exists(temp_path)
    assert os.path.getsize(temp_path) > 1000
    assert "Camera Snapshot" in caption

    # Clean up
    try:
        os.remove(temp_path)
    except Exception:
        pass
    assert not os.path.exists(temp_path)
