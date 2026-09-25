"""
Unit and Real E2E tests for sentinel.security_actions.
Labels: REAL E2E / UNIT
"""
import pytest
from unittest.mock import patch, MagicMock

from sentinel.security_actions import (
    execute_sessions,
    execute_security,
    execute_events,
    execute_audit,
    execute_lastboot,
    execute_health,
    execute_version
)

def test_sessions_real_e2e():
    """[REAL E2E] Verifies session telemetry on live workstation."""
    res = execute_sessions()
    assert "WINDOWS SESSION TELEMETRY" in res
    assert "Current User:" in res
    assert "Process Session ID:" in res
    assert "Console Session ID:" in res
    assert "Interactive Console:" in res

def test_security_posture_real_e2e():
    """[REAL E2E] Verifies security status report on live system."""
    res = execute_security()
    assert "SENTINEL SECURITY POSTURE" in res
    assert "Single-Chat Authorization:" in res
    assert "Authorized Chat ID:" in res
    assert "Command Allowlist:" in res
    assert "Zero arbitrary shell" in res

def test_events_real_e2e():
    """[REAL E2E] Verifies recent events parsing from error.log."""
    res = execute_events()
    assert "RECENT SENTINEL EVENTS" in res

def test_audit_real_e2e():
    """[REAL E2E] Verifies audit trail report."""
    res = execute_audit()
    assert "REMOTE COMMAND AUDIT TRAIL" in res
    assert "All chat IDs masked and tokens redacted" in res

def test_lastboot_real_e2e():
    """[REAL E2E] Verifies boot telemetry on live hardware."""
    res = execute_lastboot()
    assert "SYSTEM BOOT TELEMETRY" in res
    assert "Last Boot Time:" in res
    assert "System Uptime:" in res

def test_health_real_e2e():
    """[REAL E2E] Verifies component-by-component self-health check."""
    res = execute_health()
    assert "SENTINEL SELF-HEALTH CHECK" in res
    assert "Telegram Bot Token:" in res
    assert "Audit Log Storage:" in res
    assert "State File Storage:" in res

def test_health_failure_reporting_unit():
    """[UNIT] Verifies health check accurately flags missing configurations."""
    with patch("sentinel.security_actions.TELEGRAM_BOT_TOKEN", None), \
         patch("sentinel.security_actions.AUTHORIZED_CHAT_ID", None):
        res = execute_health()
        assert "UNHEALTHY" in res
        assert "FAIL" in res

def test_version_real_e2e():
    """[REAL E2E] Verifies version manifest returns v0.5.0 and runtime versions."""
    res = execute_version()
    assert "SENTINEL VERSION MANIFEST" in res
    assert "v0.5.0" in res
    assert "Python Runtime:" in res
    assert "psutil:" in res
    assert "requests:" in res
