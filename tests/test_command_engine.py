"""
Unit & Integration tests for sentinel.command_engine.
Labels: UNIT / SIMULATED / INTEGRATION
"""
import os
import json
import pytest
import threading
from unittest.mock import patch, MagicMock

import requests
from sentinel.command_engine import CommandEngine, STATE_FILE, ALLOWLIST, HELP_TEXT

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

def test_command_engine_v05_dispatch(tmp_path):
    """[UNIT] Verifies dispatch routing for new v0.5 commands."""
    test_state = tmp_path / ".test_update_state.json"

    with patch("sentinel.command_engine.STATE_FILE", test_state), \
         patch("sentinel.command_engine.is_authorized", return_value=True), \
         patch("sentinel.command_engine.send_telegram_message") as mock_send, \
         patch("sentinel.command_engine.execute_cpu", return_value="CPU OK") as mock_cpu, \
         patch("sentinel.command_engine.execute_ram", return_value="RAM OK") as mock_ram, \
         patch("sentinel.command_engine.execute_disk", return_value="Disk OK") as mock_disk, \
         patch("sentinel.command_engine.execute_ping", return_value="Ping OK") as mock_ping, \
         patch("sentinel.command_engine.execute_find", return_value="Find OK") as mock_find, \
         patch("sentinel.command_engine.execute_restart_request", return_value="Restart Prompt") as mock_restart, \
         patch("sentinel.command_engine.execute_agent", return_value="Agent OK") as mock_agent:

        engine = CommandEngine()

        commands_to_test = [
            ("/cpu", mock_cpu),
            ("/ram", mock_ram),
            ("/disk", mock_disk),
            ("/ping", mock_ping),
            ("/find README.md", mock_find),
            ("/restart", mock_restart),
            ("/agent", mock_agent),
        ]

        for idx, (cmd_text, mock_func) in enumerate(commands_to_test, start=2000):
            engine.process_update({
                "update_id": idx,
                "message": {"chat": {"id": 123456789}, "text": cmd_text}
            })
            assert mock_func.called

        # Verify argument passed to /find
        mock_find.assert_called_with("README.md")

def test_command_engine_help_text():
    """[UNIT] Verifies /help contains documentation for all v0.5 commands and confirmation notices."""
    assert "/cpu" in HELP_TEXT
    assert "/ram" in HELP_TEXT
    assert "/disk" in HELP_TEXT
    assert "/battery" in HELP_TEXT
    assert "/uptime" in HELP_TEXT
    assert "/system" in HELP_TEXT
    assert "/network" in HELP_TEXT
    assert "/wifi" in HELP_TEXT
    assert "/sessions" in HELP_TEXT
    assert "/security" in HELP_TEXT
    assert "/events" in HELP_TEXT
    assert "/audit" in HELP_TEXT
    assert "/lastboot" in HELP_TEXT
    assert "/health" in HELP_TEXT
    assert "/version" in HELP_TEXT
    assert "/restart" in HELP_TEXT
    assert "/confirm_restart" in HELP_TEXT
    assert "/find" in HELP_TEXT
    assert "/list" in HELP_TEXT
    assert "/fileinfo" in HELP_TEXT
    assert "/open" in HELP_TEXT
    assert "/ping" in HELP_TEXT
    assert "/publicip" in HELP_TEXT
    assert "/agent" in HELP_TEXT
    assert "/restart_agent" in HELP_TEXT
    assert "Requires 2-step confirmation" in HELP_TEXT
    assert "Requires local user GUI consent" in HELP_TEXT
    assert "Interactive session only" in HELP_TEXT
