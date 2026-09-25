"""
Unit & System tests for sentinel.command_auth.
Labels: UNIT / REAL E2E
"""
import pytest
from unittest.mock import patch
from sentinel.command_auth import (
    is_authorized,
    get_process_session_id,
    get_active_console_session_id,
    verify_interactive_session
)
from sentinel.config import mask_chat_id

def test_is_authorized_matching_and_mismatch():
    """[UNIT] Verifies strict single-chat authorization and type-safe comparisons."""
    with patch("sentinel.command_auth.AUTHORIZED_CHAT_ID", "123456789"):
        assert is_authorized("123456789") is True
        assert is_authorized(123456789) is True
        assert is_authorized(" 123456789 ") is True
        assert is_authorized("987654321") is False
        assert is_authorized(None) is False
        assert is_authorized("") is False

def test_is_authorized_missing_config():
    """[UNIT] Verifies all commands are rejected if AUTHORIZED_CHAT_ID is missing."""
    with patch("sentinel.command_auth.AUTHORIZED_CHAT_ID", None):
        assert is_authorized("123456789") is False

def test_mask_chat_id():
    """[UNIT] Verifies chat ID masking rules."""
    assert mask_chat_id("123456789") == "123****89"
    assert mask_chat_id("9876543210") == "987****10"
    assert mask_chat_id("1234") == "****"
    assert mask_chat_id(None) == "None"

def test_real_interactive_session():
    """[REAL E2E] Verifies active Windows console session detection on real system."""
    proc_sid = get_process_session_id()
    active_sid = get_active_console_session_id()
    
    assert proc_sid >= 0, "Process Session ID must be non-negative"
    assert active_sid >= 0, "Active Console Session ID must be non-negative"
    
    is_valid, reason = verify_interactive_session()
    # In interactive desktop, proc_sid should match active_sid and not be 0
    if proc_sid != 0 and proc_sid == active_sid:
        assert is_valid is True
        assert reason == ""

def test_verify_interactive_session_session_0_rejection():
    """[UNIT] Verifies rejection when process is running in Session 0."""
    with patch("sentinel.command_auth.get_process_session_id", return_value=0), \
         patch("sentinel.command_auth.get_active_console_session_id", return_value=1):
        is_valid, reason = verify_interactive_session()
        assert is_valid is False
        assert "Session 0" in reason

def test_verify_interactive_session_mismatch_rejection():
    """[UNIT] Verifies rejection when process session does not match console session."""
    with patch("sentinel.command_auth.get_process_session_id", return_value=2), \
         patch("sentinel.command_auth.get_active_console_session_id", return_value=1):
        is_valid, reason = verify_interactive_session()
        assert is_valid is False
        assert "does not match active interactive console" in reason
