import os
import sys
import socket
import platform
import getpass
from typing import Dict, Any, Optional

def get_battery_info() -> Dict[str, str]:
    """
    Retrieves current battery percentage and power plug status.
    Uses psutil with graceful fallback to ctypes Windows API or 'Unavailable'.
    """
    # Attempt 1: psutil
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery is not None:
            percent = f"{int(round(battery.percent))}%"
            power = "AC" if battery.power_plugged else "Battery"
            return {
                "percent": percent,
                "power_source": power
            }
    except Exception:
        pass

    # Attempt 2: Windows ctypes GetSystemPowerStatus
    try:
        import ctypes
        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", ctypes.c_byte),
                ("BatteryFlag", ctypes.c_byte),
                ("BatteryLifePercent", ctypes.c_byte),
                ("SystemStatusFlag", ctypes.c_byte),
                ("BatteryLifeTime", ctypes.c_ulong),
                ("BatteryFullLifeTime", ctypes.c_ulong),
            ]
        status = SYSTEM_POWER_STATUS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            percent_val = status.BatteryLifePercent
            percent_str = f"{percent_val}%" if percent_val != 255 else "Unavailable"
            power_str = "AC" if status.ACLineStatus == 1 else ("Battery" if status.ACLineStatus == 0 else "Unavailable")
            return {
                "percent": percent_str,
                "power_source": power_str
            }
    except Exception:
        pass

    return {
        "percent": "Unavailable",
        "power_source": "Unavailable"
    }

def get_username() -> str:
    """Safely retrieves the current active user name."""
    try:
        return getpass.getuser()
    except Exception:
        return os.getenv("USERNAME", "Unknown User")

def get_os_info() -> str:
    """Returns a clean formatted OS string (e.g. Windows 11)."""
    try:
        release = platform.release()
        system = platform.system()
        # Windows 11 platform.release() may return '10' on some Python versions or '11'
        # Windows 11 build is >= 22000
        version = platform.version()
        if system == "Windows":
            try:
                build = int(version.split(".")[2])
                if build >= 22000:
                    return "Windows 11"
            except Exception:
                pass
            return f"Windows {release}"
        return f"{system} {release}"
    except Exception:
        return "Windows 11"

def get_system_metadata() -> Dict[str, Any]:
    """Gathers high-level system metadata for notifications."""
    hostname = socket.gethostname()
    battery = get_battery_info()
    return {
        "device": f"ASUS TUF A15 ({hostname})",
        "hostname": hostname,
        "os": get_os_info(),
        "user": get_username(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "battery_percent": battery["percent"],
        "power_source": battery["power_source"]
    }
