"""
Regression tests for existing Sentinel Boot Tracker functionality.
Verifies startup, shutdown, lock, unlock, location, and telemetry do not break.
Labels: REAL E2E / UNIT
"""
import pytest
from unittest.mock import patch, MagicMock
from sentinel.telegram import send_telegram_alert
from sentinel.system_info import get_battery_info, get_os_info, get_system_metadata
from sentinel.location import get_location_telemetry, load_location_cache
from sentinel.network import get_network_info

def test_telemetry_collection_real_e2e():
    """[REAL E2E] Verifies system, battery, and network telemetry on real hardware."""
    sys_meta = get_system_metadata()
    assert "device" in sys_meta
    assert "hostname" in sys_meta
    assert "battery_percent" in sys_meta
    assert "power_source" in sys_meta

    bat = get_battery_info()
    assert "percent" in bat
    assert "power_source" in bat

    net = get_network_info(timeout=3.0)
    assert "ip" in net
    assert "location" in net

def test_location_telemetry_real_e2e():
    """[REAL E2E] Verifies 3-tier location telemetry."""
    loc = get_location_telemetry(timeout=3.0)
    assert "location_tier" in loc
    assert loc["location_tier"] in ["windows_live", "cached", "ip_fallback"]
    assert "source" in loc
    assert "maps_url" in loc

def test_existing_alert_pipeline_startup_unit():
    """[UNIT] Verifies startup alert dispatch pipeline."""
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        res = send_telegram_alert("startup")
        assert res is True
        assert mock_post.called
        payload = mock_post.call_args[1]["json"]
        assert "SENTINEL ALERT — SYSTEM STARTUP" in payload["text"]

def test_existing_alert_pipeline_shutdown_unit():
    """[UNIT] Verifies shutdown alert dispatch pipeline."""
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        res = send_telegram_alert("shutdown")
        assert res is True
        assert mock_post.called
        payload = mock_post.call_args[1]["json"]
        assert "SENTINEL ALERT — SYSTEM SHUTDOWN" in payload["text"]

def test_existing_alert_pipeline_lock_unlock_unit():
    """[UNIT] Verifies lock and unlock alert dispatches."""
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        assert send_telegram_alert("lock") is True
        payload_lock = mock_post.call_args[1]["json"]
        assert "WORKSTATION LOCKED" in payload_lock["text"]

        assert send_telegram_alert("unlock") is True
        payload_unlock = mock_post.call_args[1]["json"]
        assert "WORKSTATION UNLOCKED" in payload_unlock["text"]
