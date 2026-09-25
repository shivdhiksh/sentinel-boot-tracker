"""
Unit and Real E2E tests for sentinel.agent_actions.
Labels: REAL E2E / UNIT
"""
import pytest
from unittest.mock import patch, MagicMock

from sentinel.agent_actions import (
    execute_agent,
    execute_restart_agent
)

def test_execute_agent_real_e2e():
    """[REAL E2E] Verifies agent diagnostics on live process."""
    res = execute_agent()
    assert "SENTINEL AGENT DIAGNOSTICS" in res
    assert "Process ID (PID):" in res
    assert "Context User:" in res
    assert "Process Session ID:" in res
    assert "Agent Uptime:" in res
    assert "Memory Usage (RSS):" in res
    assert "CPU Load:" in res
    assert "Active Threads:" in res

def test_execute_restart_agent_unit():
    """
    [UNIT] Verifies agent restart sequence.
    Mocks threading.Thread and inspects deferred target to ensure it invokes
    subprocess.Popen with detached flags and os._exit without terminating the test suite.
    """
    mock_thread_instance = MagicMock()
    with patch("sentinel.agent_actions.threading.Thread", return_value=mock_thread_instance) as mock_thread_cls, \
         patch("sentinel.agent_actions.subprocess.Popen") as mock_popen, \
         patch("sentinel.agent_actions.os._exit") as mock_exit, \
         patch("sentinel.agent_actions.time.sleep") as mock_sleep:

        res = execute_restart_agent()
        assert "Restart initiated" in res
        assert mock_thread_cls.called
        assert mock_thread_instance.start.called

        # Extract and safely invoke deferred target synchronously
        deferred_target = mock_thread_cls.call_args[1].get("target")
        assert deferred_target is not None
        deferred_target()

        mock_sleep.assert_called_once_with(1.5)
        assert mock_popen.called
        assert mock_exit.called
        mock_exit.assert_called_once_with(0)

def test_execute_restart_agent_debounce_unit():
    """[UNIT] Verifies repeated /restart_agent calls while pending are debounced."""
    import sentinel.agent_actions as aa
    with aa._agent_restart_lock:
        aa._agent_restart_pending = True

    try:
        res = execute_restart_agent()
        assert "already in progress" in res
    finally:
        with aa._agent_restart_lock:
            aa._agent_restart_pending = False

