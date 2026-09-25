"""
Unit, Simulated, Real E2E, and Inspection tests for sentinel.network_actions.
Labels: REAL E2E / UNIT / SIMULATED / STATIC/INSPECTION
"""
import socket
import pytest
from unittest.mock import patch, MagicMock

from sentinel.network_actions import (
    execute_ping,
    execute_publicip,
    execute_network,
    execute_wifi
)

def test_ping_real_e2e():
    """[REAL E2E] Verifies predefined endpoint latency testing."""
    res = execute_ping()
    assert "SENTINEL CONNECTIVITY PING" in res
    assert "Cloudflare DNS:" in res
    assert "Google DNS:" in res
    assert "Predefined trusted endpoints only" in res

def test_ping_timeout_simulated():
    """[SIMULATED] Verifies ping handles socket timeout gracefully."""
    with patch("socket.create_connection", side_effect=socket.timeout):
        res = execute_ping()
        assert "Timeout" in res

def test_publicip_real_e2e():
    """[REAL E2E] Verifies public IP detection on live network."""
    res = execute_publicip()
    assert "SENTINEL PUBLIC IP REPORT" in res
    assert "Public IP:" in res
    assert "IP geolocation is approximate" in res

def test_publicip_unavailable_unit():
    """[UNIT] Verifies public IP report when network provider returns unavailable."""
    with patch("sentinel.network_actions.get_network_info", return_value={"ip": "Unavailable", "location": "Unavailable"}):
        res = execute_publicip()
        assert "Unavailable" in res

def test_network_interfaces_real_e2e():
    """[REAL E2E] Verifies active network adapters listing on live system."""
    res = execute_network()
    assert "SENTINEL NETWORK INTERFACES" in res
    assert ("Adapter:" in res) or ("No active physical" in res)
    assert "Public Internet IP:" in res

def test_wifi_telemetry_real_e2e():
    """[REAL E2E] Verifies Wi-Fi telemetry querying without exposing credentials."""
    res = execute_wifi()
    assert "SENTINEL WI-FI TELEMETRY" in res
    assert ("<b>Status:</b>" in res) or ("unavailable" in res.lower())
    assert "Credentials, passwords, and security keys are never queried or exposed" in res

def test_wifi_unavailable_unit():
    """[UNIT] Verifies Wi-Fi handler when netsh returns non-zero exit code."""
    mock_proc = MagicMock()
    mock_proc.returncode = 1
    mock_proc.stdout = ""
    with patch("subprocess.run", return_value=mock_proc):
        res = execute_wifi()
        assert "Wi-Fi subsystem unavailable" in res

def test_wifi_never_queries_key_clear_inspection():
    """
    [STATIC/INSPECTION]
    Static analysis check verifying netsh commands in network_actions NEVER include 'key=clear'
    or password export flags.
    """
    import inspect
    import sentinel.network_actions as na

    source_code = inspect.getsource(na)
    assert "key=clear" not in source_code.lower()
    assert "export profile" not in source_code.lower()
