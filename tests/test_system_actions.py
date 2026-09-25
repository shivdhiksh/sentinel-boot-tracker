"""
Unit and Real E2E tests for sentinel.system_actions.
Labels: REAL E2E / UNIT
"""
import pytest
from unittest.mock import patch, MagicMock

from sentinel.system_actions import (
    execute_cpu,
    execute_ram,
    execute_disk,
    execute_battery,
    execute_uptime,
    execute_system
)

def test_execute_cpu_real_e2e():
    """[REAL E2E] Verifies CPU telemetry on live hardware."""
    res = execute_cpu()
    assert "SENTINEL CPU TELEMETRY" in res
    assert "Load:" in res
    assert "Cores:" in res
    assert "Clock Speed:" in res

def test_execute_ram_real_e2e():
    """[REAL E2E] Verifies RAM telemetry on live hardware."""
    res = execute_ram()
    assert "SENTINEL RAM TELEMETRY" in res
    assert "Memory Load:" in res
    assert "Used / Total:" in res
    assert "Available:" in res
    assert "Swap / Pagefile:" in res

def test_execute_disk_real_e2e():
    """[REAL E2E] Verifies disk usage on live hardware."""
    res = execute_disk()
    assert "SENTINEL DISK USAGE" in res
    assert ("Drive " in res) or ("No local fixed storage" in res)

def test_execute_battery_real_e2e():
    """[REAL E2E] Verifies battery telemetry on live hardware."""
    res = execute_battery()
    assert "SENTINEL BATTERY TELEMETRY" in res
    assert "Level:" in res
    assert "Power State:" in res

def test_execute_uptime_real_e2e():
    """[REAL E2E] Verifies uptime report on live hardware."""
    res = execute_uptime()
    assert "WINDOWS UPTIME REPORT" in res
    assert "System Uptime:" in res
    assert "Booted At:" in res

def test_execute_system_real_e2e():
    """[REAL E2E] Verifies system overview on live hardware."""
    res = execute_system()
    assert "SENTINEL SYSTEM OVERVIEW" in res
    assert "Hostname:" in res
    assert "Active User:" in res
    assert "OS Version:" in res
    assert "Processor:" in res
    assert "Total RAM:" in res
    assert "GPU:" in res

def test_system_actions_error_handling_unit():
    """[UNIT] Verifies graceful fallback when psutil or registry fails."""
    with patch("psutil.cpu_percent", side_effect=RuntimeError("psutil error")), \
         patch("psutil.virtual_memory", side_effect=RuntimeError("ram error")), \
         patch("psutil.disk_partitions", side_effect=RuntimeError("disk error")), \
         patch("psutil.boot_time", side_effect=RuntimeError("boot error")):

        cpu_out = execute_cpu()
        assert "Unavailable" in cpu_out

        ram_out = execute_ram()
        assert "Unavailable" in ram_out

        disk_out = execute_disk()
        assert "SENTINEL DISK USAGE" in disk_out

        uptime_out = execute_uptime()
        assert "Unavailable" in uptime_out
