"""
Unit tests for sentinel.command_audit.
Labels: UNIT
"""
import pytest
from unittest.mock import patch, MagicMock
from sentinel.command_audit import log_command_audit

def test_log_command_audit_success():
    """[UNIT] Verifies structured INFO logging for authorized successful command."""
    mock_logger = MagicMock()
    with patch("sentinel.command_audit.logger", mock_logger):
        log_command_audit(
            command="/status",
            chat_id="123456789",
            is_authorized_user=True,
            result="SUCCESS"
        )
        assert mock_logger.info.called
        log_msg = mock_logger.info.call_args[0][0]
        assert "Remote command" in log_msg
        assert "User: authorized" in log_msg
        assert "Chat ID: 123****89" in log_msg
        assert "Command: /status" in log_msg
        assert "Result: SUCCESS" in log_msg
        assert "Timestamp:" in log_msg

def test_log_command_audit_rejection():
    """[UNIT] Verifies structured WARN logging for unauthorized rejection."""
    mock_logger = MagicMock()
    with patch("sentinel.command_audit.logger", mock_logger):
        log_command_audit(
            command="/shutdown",
            chat_id="987654321",
            is_authorized_user=False,
            result="REJECTED",
            reason="Unauthorized chat ID"
        )
        assert mock_logger.warning.called
        log_msg = mock_logger.warning.call_args[0][0]
        assert "Remote command" in log_msg
        assert "User: unauthorized" in log_msg
        assert "Chat ID: 987****21" in log_msg
        assert "Command: /shutdown" in log_msg
        assert "Result: REJECTED" in log_msg
        assert "Reason: Unauthorized chat ID" in log_msg

def test_log_command_audit_token_redaction():
    """[UNIT] Verifies bot token is redacted from audit logs."""
    fake_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    mock_logger = MagicMock()
    with patch("sentinel.config.TELEGRAM_BOT_TOKEN", fake_token), \
         patch("sentinel.command_audit.logger", mock_logger):
        log_command_audit(
            command=f"/status?token={fake_token}",
            chat_id="123456789",
            is_authorized_user=True,
            result="SUCCESS"
        )
        log_msg = mock_logger.info.call_args[0][0]
        assert fake_token not in log_msg
        assert "[REDACTED_TOKEN]" in log_msg
