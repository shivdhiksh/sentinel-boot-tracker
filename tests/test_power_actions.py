"""
Unit and Safety tests for sentinel.power_actions.
Labels: UNIT / SAFETY
"""
import time
import pytest
from unittest.mock import patch, MagicMock

from sentinel.power_actions import (
    execute_lock,
    execute_shutdown_request,
    execute_confirm_shutdown,
    execute_restart_request,
    execute_confirm_restart
)

@pytest.fixture(autouse=True)
def prevent_real_power_actions(monkeypatch):
    """
    SAFETY INTERCEPTOR:
    Hard-blocks any invocation of shutdown.exe (both shutdown /s and reboot /r) across all tests.
    Raises RuntimeError immediately if invoked.
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
    monkeypatch.setattr("sentinel.power_actions.subprocess.Popen", safe_popen)


def test_execute_lock_unit():
    """[UNIT] Verifies workstation lock API invocation."""
    with patch("ctypes.windll.user32.LockWorkStation", return_value=1):
        res = execute_lock()
        assert res == "✅ Workstation locked"


def test_shutdown_confirmation_unit():
    """[UNIT] Verifies two-step shutdown request and timeout behavior."""
    chat_a = "123456789"
    prompt = execute_shutdown_request(chat_a)
    assert "Confirm shutdown" in prompt
    assert "/confirm_shutdown" in prompt


def test_restart_confirmation_state_machine():
    """
    [UNIT] Verifies two-step restart confirmation, 30s monotonic expiration, and chat binding.
    GUARANTEE: Real shutdown.exe can NEVER execute.
    """
    chat_a = "123456789"
    chat_b = "987654321"

    # Step 1: Initial restart request
    prompt = execute_restart_request(chat_a)
    assert "Confirm restart" in prompt
    assert "/confirm_restart" in prompt
    assert "30 seconds" in prompt

    # Step 2: Confirmation from mismatched chat ID is rejected
    ok_b, msg_b = execute_confirm_restart(chat_b)
    assert ok_b is False
    assert "chat ID mismatch" in msg_b

    # Step 3: Expired confirmation (>30s) is rejected
    with patch("time.monotonic", return_value=time.monotonic() + 35.0):
        ok_exp, msg_exp = execute_confirm_restart(chat_a)
        assert ok_exp is False
        assert "expired" in msg_exp

    # Step 4: Valid confirmation within 30s accepted
    execute_restart_request(chat_a)

    mock_thread_instance = MagicMock()
    with patch("sentinel.power_actions.threading.Thread", return_value=mock_thread_instance) as mock_thread_cls, \
         patch("sentinel.power_actions.subprocess.Popen") as mock_popen, \
         patch("sentinel.power_actions.time.sleep") as mock_sleep:

        ok_valid, msg_valid = execute_confirm_restart(chat_a)
        assert ok_valid is True
        assert "Restart command accepted" in msg_valid

        # Assert background thread creation
        assert mock_thread_cls.called
        assert mock_thread_instance.start.called

        # Safely execute the deferred target synchronously to verify command args
        deferred_target = mock_thread_cls.call_args[1].get("target")
        assert deferred_target is not None
        deferred_target()

        mock_sleep.assert_called_once_with(1.5)
        mock_popen.assert_called_once()
        cmd_args = mock_popen.call_args[0][0]
        assert cmd_args[0] == "shutdown.exe"
        assert "/r" in cmd_args
        assert "/t" in cmd_args
        assert "5" in cmd_args
        assert "Sentinel remote restart initiated" in cmd_args


def test_confirm_restart_without_request():
    """[UNIT] Verifies /confirm_restart fails if no request was pending."""
    # Reset pending state
    import sentinel.power_actions as pa
    with pa._restart_lock:
        pa._pending_restart = None

    ok, msg = execute_confirm_restart("123456789")
    assert ok is False
    assert "No active restart request found" in msg
