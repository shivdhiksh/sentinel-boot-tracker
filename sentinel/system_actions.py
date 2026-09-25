"""
Sentinel System Actions Module:
Provides safe system telemetry inspection handlers:
/cpu, /ram, /disk, /battery, /uptime, /system.
Bounded execution, safe fallbacks, zero shell injection.
"""
import os
import sys
import time
import socket
import platform
from typing import Dict, Any, List

import psutil

from .config import logger, sanitize
from .system_info import get_battery_info, get_os_info, get_username

def execute_cpu() -> str:
    """
    Returns CPU utilization and core topology safely.
    """
    try:
        overall_load = psutil.cpu_percent(interval=0.2)
        load_str = f"{overall_load:.1f}%"
    except Exception as exc:
        logger.warning(f"execute_cpu error: {sanitize(str(exc))}")
        load_str = "Unavailable"

    try:
        physical_cores = psutil.cpu_count(logical=False) or "N/A"
        logical_cores = psutil.cpu_count(logical=True) or "N/A"
    except Exception:
        physical_cores = "N/A"
        logical_cores = "N/A"

    try:
        freq = psutil.cpu_freq()
        if freq and freq.current:
            freq_str = f"{freq.current:.0f} MHz"
            if freq.max:
                freq_str += f" (Max: {freq.max:.0f} MHz)"
        else:
            freq_str = "Unavailable"
    except Exception:
        freq_str = "Unavailable"

    lines = [
        "⚙️ <b>SENTINEL CPU TELEMETRY</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📊 <b>Load:</b> <code>{load_str}</code>",
        f"🧩 <b>Cores:</b> {physical_cores} Physical / {logical_cores} Logical",
        f"⚡ <b>Clock Speed:</b> {freq_str}",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]
    return "\n".join(lines)


def execute_ram() -> str:
    """
    Returns RAM used/available/total and swap utilization safely.
    """
    try:
        vm = psutil.virtual_memory()
        total_gb = vm.total / (1024 ** 3)
        used_gb = vm.used / (1024 ** 3)
        avail_gb = vm.available / (1024 ** 3)
        ram_percent = f"{vm.percent:.1f}%"
        ram_detail = f"{used_gb:.2f} GB / {total_gb:.2f} GB"
        avail_detail = f"{avail_gb:.2f} GB"
    except Exception as exc:
        logger.warning(f"execute_ram error: {sanitize(str(exc))}")
        ram_percent = "Unavailable"
        ram_detail = "Unavailable"
        avail_detail = "Unavailable"

    try:
        sm = psutil.swap_memory()
        swap_total = sm.total / (1024 ** 3)
        swap_used = sm.used / (1024 ** 3)
        swap_str = f"{sm.percent:.1f}% ({swap_used:.2f} / {swap_total:.2f} GB)"
    except Exception:
        swap_str = "Unavailable"

    lines = [
        "🧠 <b>SENTINEL RAM TELEMETRY</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"📊 <b>Memory Load:</b> <code>{ram_percent}</code>",
        f"📈 <b>Used / Total:</b> {ram_detail}",
        f"📉 <b>Available:</b> {avail_detail}",
        f"🔄 <b>Swap / Pagefile:</b> {swap_str}",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]
    return "\n".join(lines)


def execute_disk() -> str:
    """
    Returns disk usage for approved/local drives safely.
    """
    lines = [
        "💾 <b>SENTINEL DISK USAGE</b>",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    found_drives = 0
    try:
        partitions = psutil.disk_partitions(all=False)
        for part in partitions:
            # Skip non-fixed partitions or unready drives (e.g. CD-ROM)
            if "cdrom" in part.opts or not part.fstype:
                continue
            try:
                usage = psutil.disk_usage(part.mountpoint)
                total_gb = usage.total / (1024 ** 3)
                used_gb = usage.used / (1024 ** 3)
                free_gb = usage.free / (1024 ** 3)
                pct = usage.percent

                lines.append(f"💿 <b>Drive {part.mountpoint}</b> ({part.fstype or 'NTFS'})")
                lines.append(f"   Usage: <code>{pct:.1f}%</code> ({used_gb:.1f} / {total_gb:.1f} GB)")
                lines.append(f"   Free: <code>{free_gb:.1f} GB</code>\n")
                found_drives += 1
            except (PermissionError, OSError):
                continue
    except Exception as exc:
        logger.warning(f"execute_disk error: {sanitize(str(exc))}")

    if found_drives == 0:
        lines.append("⚠️ No local fixed storage partitions detected.")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def execute_battery() -> str:
    """
    Returns battery percentage, charging state, and available telemetry.
    """
    bat = get_battery_info()
    percent = bat.get("percent", "Unavailable")
    power_src = bat.get("power_source", "Unavailable")

    status_str = "Plugged In" if power_src == "AC" else "On Battery"
    secs_left_str = "N/A"

    try:
        ps_bat = psutil.sensors_battery()
        if ps_bat:
            if ps_bat.power_plugged:
                status_str = "Charging / AC Power" if ps_bat.percent < 100 else "Fully Charged (AC)"
            else:
                status_str = "Discharging"

            if ps_bat.secsleft and ps_bat.secsleft != psutil.POWER_TIME_UNLIMITED and ps_bat.secsleft != psutil.POWER_TIME_UNKNOWN:
                mins_left = ps_bat.secsleft // 60
                hrs = mins_left // 60
                mins = mins_left % 60
                secs_left_str = f"~{hrs}h {mins}m remaining"
    except Exception:
        pass

    lines = [
        "🔋 <b>SENTINEL BATTERY TELEMETRY</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"⚡ <b>Level:</b> <code>{percent}</code>",
        f"🔌 <b>Power State:</b> {status_str}",
        f"⏱️ <b>Estimated Runtime:</b> {secs_left_str}",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]
    return "\n".join(lines)


def execute_uptime() -> str:
    """
    Returns Windows uptime calculated from system boot time.
    """
    try:
        boot_ts = psutil.boot_time()
        diff = max(0, int(time.time() - boot_ts))
        days = diff // 86400
        hrs = (diff % 86400) // 3600
        mins = (diff % 3600) // 60
        secs = diff % 60

        uptime_parts = []
        if days > 0:
            uptime_parts.append(f"{days}d")
        uptime_parts.append(f"{hrs}h")
        uptime_parts.append(f"{mins}m")
        uptime_parts.append(f"{secs}s")
        uptime_str = " ".join(uptime_parts)

        boot_dt = time.strftime("%Y-%m-%d %I:%M:%S %p", time.localtime(boot_ts))
    except Exception as exc:
        logger.warning(f"execute_uptime error: {sanitize(str(exc))}")
        uptime_str = "Unavailable"
        boot_dt = "Unavailable"

    lines = [
        "⏱️ <b>WINDOWS UPTIME REPORT</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"🚀 <b>System Uptime:</b> <code>{uptime_str}</code>",
        f"🕒 <b>Booted At:</b> {boot_dt}",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]
    return "\n".join(lines)


def execute_system() -> str:
    """
    Returns safe system summary: Windows edition, hostname, CPU, RAM, and GPU.
    Zero shell execution.
    """
    os_info = get_os_info()
    hostname = socket.gethostname()
    username = get_username()
    architecture = platform.machine()

    # CPU Model
    cpu_model = platform.processor() or "Unknown CPU"

    # Total RAM
    try:
        vm = psutil.virtual_memory()
        total_ram = f"{vm.total / (1024 ** 3):.1f} GB"
    except Exception:
        total_ram = "Unavailable"

    # GPU Model (safe query without shell)
    gpu_model = "Unavailable"
    try:
        # Check Windows registry for Display Adapter description
        import winreg
        key_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as base_key:
            gpus: List[str] = []
            for i in range(16):
                try:
                    sub_name = f"{i:04d}"
                    with winreg.OpenKey(base_key, sub_name) as sub_key:
                        desc, _ = winreg.QueryValueEx(sub_key, "DriverDesc")
                        if desc and desc not in gpus:
                            gpus.append(str(desc))
                except (OSError, FileNotFoundError):
                    continue
            if gpus:
                gpu_model = ", ".join(gpus)
    except Exception:
        pass

    lines = [
        "💻 <b>SENTINEL SYSTEM OVERVIEW</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"💻 <b>Hostname:</b> {hostname}",
        f"👤 <b>Active User:</b> {username}",
        f"🪟 <b>OS Version:</b> {os_info} ({architecture})",
        f"⚙️ <b>Processor:</b> {cpu_model}",
        f"🧠 <b>Total RAM:</b> {total_ram}",
        f"🎮 <b>GPU:</b> {gpu_model}",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]
    return "\n".join(lines)
