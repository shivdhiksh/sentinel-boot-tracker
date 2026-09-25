"""
Unit & Integration tests for sentinel.command_engine.
Labels: UNIT / SIMULATED
"""
import os
import json
import pytest
import threading
from unittest.mock import patch, MagicMock

import requests
from sentinel.command_engine import CommandEngine, STATE_FILE

def test_command_engine_deduplication(tmp_path):
    """[UNIT] Verifies duplicate update_ids are processed exactly once."""
    test_state = tmp_path / ".test_update_state.json"
    
    with patch("sentinel.command_engine.STATE_FILE", test_state), \
         patch("sentinel.command_engine.is_authorized", return_value=True), \
         patch("sentinel.command_engine.send_telegram_message") as mock_send, \
         patch("sentinel.command_engine.execute_status", return_value="Status OK"):

        engine = CommandEngine()
        
        update = {
            "update_id": 1001,
            "message": {
                "chat": {"id": 123456789},
                "text": "/status"
            }
        }

        # First delivery -> Processed
        engine.process_update(update)
        assert mock_send.call_count == 1
        assert engine.last_update_id == 1001
        assert 1001 in engine.processed_update_ids

        # Duplicate delivery -> Skipped
        engine.process_update(update)
        assert mock_send.call_count == 1  # Not called again

def test_command_engine_unauthorized_rejection(tmp_path):
    """[UNIT] Verifies unauthorized sender is rejected and command never executes."""
    test_state = tmp_path / ".test_update_state.json"
    
    with patch("sentinel.command_engine.STATE_FILE", test_state), \
         patch("sentinel.command_engine.is_authorized", return_value=False), \
         patch("sentinel.command_engine.send_telegram_message") as mock_send, \
         patch("sentinel.command_engine.execute_shutdown_request") as mock_shutdown:

        engine = CommandEngine()
        
        update = {
            "update_id": 1002,
            "message": {
                "chat": {"id": 999999999},
                "text": "/shutdown"
            }
        }

        engine.process_update(update)
        assert mock_shutdown.called is False
        assert mock_send.called is True
        sent_msg = mock_send.call_args[0][0]
        assert "Access Denied" in sent_msg

def test_command_engine_unknown_command(tmp_path):
    """[UNIT] Verifies unknown command is safely rejected with help guidance."""
    test_state = tmp_path / ".test_update_state.json"
    
    with patch("sentinel.command_engine.STATE_FILE", test_state), \
         patch("sentinel.command_engine.is_authorized", return_value=True), \
         patch("sentinel.command_engine.send_telegram_message") as mock_send:

        engine = CommandEngine()
        
        update = {
            "update_id": 1003,
            "message": {
                "chat": {"id": 123456789},
                "text": "/malicious_eval 'rm -rf /'"
            }
        }

        engine.process_update(update)
        assert mock_send.called is True
        sent_msg = mock_send.call_args[0][0]
        assert "Unknown command" in sent_msg

def test_command_engine_state_persistence_across_restart(tmp_path):
    """[UNIT] Verifies update state persists across engine restarts."""
    test_state = tmp_path / ".test_update_state.json"
    
    with patch("sentinel.command_engine.STATE_FILE", test_state), \
         patch("sentinel.command_engine.is_authorized", return_value=True), \
         patch("sentinel.command_engine.send_telegram_message"), \
         patch("sentinel.command_engine.execute_lock", return_value="Locked"):

        engine1 = CommandEngine()
        engine1.process_update({
            "update_id": 5555,
            "message": {"chat": {"id": 123456789}, "text": "/lock"}
        })

        # Restart Sentinel engine
        engine2 = CommandEngine()
        assert engine2.last_update_id == 5555
        assert 5555 in engine2.processed_update_ids

def test_command_engine_network_failure_backoff():
    """[SIMULATED] Verifies polling loop gracefully handles network exceptions and stops cleanly."""
    stop_event = threading.Event()
    
    mock_get = MagicMock(side_effect=requests.RequestException("Connection dropped"))
    with patch("sentinel.command_engine.get_telegram_updates", mock_get):
        engine = CommandEngine(stop_event=stop_event)
        
        # Stop after 0.5 seconds
        timer = threading.Timer(0.5, stop_event.set)
        timer.start()
        
        engine.run_polling_loop()
        assert mock_get.called
