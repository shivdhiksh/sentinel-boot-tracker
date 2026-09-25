"""
Sentinel Network Diagnostics Module:
Implements safe network telemetry handlers:
/ping, /publicip, /network, /wifi.
Strictly predefined endpoints, zero shell evaluation,
and credential-safe Wi-Fi telemetry.
"""
import time
import socket
import subprocess
from typing import Dict, Any, List

import psutil

from .config import logger, sanitize
from .network import get_network_info

PREDEFINED_PING_TARGETS = [
    ("Cloudflare DNS", "1.1.1.1", 53),
    ("Google DNS", "8.8.8.8", 53),
    ("Telegram Bot API", "api.telegram.org", 443)
]


def execute_ping() -> str:
    """
    Performs safe connectivity tests against predefined endpoints using non-blocking socket connect.
    Measures latency in milliseconds with bounded 2.0s timeouts.
    Never accepts arbitrary user hosts.
    """
    lines = [
        "📡 <b>SENTINEL CONNECTIVITY PING</b>",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    for label, host, port in PREDEFINED_PING_TARGETS:
        t0 = time.perf_counter()
        try:
            sock = socket.create_connection((host, port), timeout=2.0)
            sock.close()
            latency_ms = (time.perf_counter() - t0) * 1000.0
            status_icon = "🟢" if latency_ms < 100 else ("🟡" if latency_ms < 300 else "🟠")
            lines.append(f"{status_icon} <b>{label}:</b> <code>{latency_ms:.1f} ms</code>")
        except socket.timeout:
            lines.append(f"🔴 <b>{label}:</b> <code>Timeout (>2000 ms)</code>")
        except Exception as exc:
            lines.append(f"🔴 <b>{label}:</b> <code>Unreachable ({sanitize(str(exc))})</code>")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔒 <i>Predefined trusted endpoints only.</i>")
    return "\n".join(lines)


def execute_publicip() -> str:
    """
    Returns public IP and region using the existing bounded multi-provider network engine.
    """
    try:
        net = get_network_info(timeout=3.5)
        ip = net.get("ip", "Unavailable")
        location = net.get("location", "Unavailable")
        maps_url = net.get("maps_url")
    except Exception as exc:
        logger.warning(f"execute_publicip error: {sanitize(str(exc))}")
        ip = "Unavailable"
        location = "Unavailable"
        maps_url = None

    status_icon = "🟢" if ip != "Unavailable" else "🔴"
    lines = [
        "🌐 <b>SENTINEL PUBLIC IP REPORT</b>",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"{status_icon} <b>Public IP:</b> <code>{ip}</code>",
        f"📍 <b>Region / ISP:</b> {location}",
    ]
    if maps_url:
        lines.append(f"\n🗺️ <b>Approximate Map:</b>\n{maps_url}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("⚠️ <i>IP geolocation is approximate.</i>")
    return "\n".join(lines)


def execute_network() -> str:
    """
    Returns active network adapters, IP addresses, netmasks, and overall connectivity.
    """
    lines = [
        "🔌 <b>SENTINEL NETWORK INTERFACES</b>",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    try:
        net_stats = psutil.net_if_stats()
        net_addrs = psutil.net_if_addrs()

        active_adapters = 0
        for iface_name, addrs in net_addrs.items():
            # Skip loopback
            if "loopback" in iface_name.lower():
                continue

            stat = net_stats.get(iface_name)
            is_up = stat.isup if stat else False
            speed = f"{stat.speed} Mbps" if (stat and stat.speed > 0) else "Auto"

            ipv4_info: List[str] = []
            for addr in addrs:
                if addr.family == socket.AF_INET:
                    ipv4_info.append(f"{addr.address} (Netmask: {addr.netmask or 'N/A'})")

            if ipv4_info and is_up:
                active_adapters += 1
                icon = "🟢" if is_up else "⚪"
                lines.append(f"{icon} <b>Adapter:</b> <code>{sanitize(iface_name)}</code>")
                lines.append(f"   Status: {'UP' if is_up else 'DOWN'} | Speed: {speed}")
                for ip_str in ipv4_info:
                    lines.append(f"   IPv4: <code>{ip_str}</code>")
                lines.append("")

        if active_adapters == 0:
            lines.append("⚠️ No active physical or wireless adapters detected.")

    except Exception as exc:
        logger.warning(f"execute_network error: {sanitize(str(exc))}")
        lines.append(f"❌ Error collecting interfaces: {sanitize(str(exc))}")

    # Public IP check
    try:
        net = get_network_info(timeout=2.0)
        public_ip = net.get("ip", "Unavailable")
        lines.append(f"🌐 <b>Public Internet IP:</b> <code>{public_ip}</code>")
    except Exception:
        pass

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def execute_wifi() -> str:
    """
    Returns connected Wi-Fi adapter state, SSID, BSSID, radio type, and signal quality.
    STRICTLY NEVER exposes passwords, keys, or security profiles.
    Zero shell execution.
    """
    lines = [
        "📶 <b>SENTINEL WI-FI TELEMETRY</b>",
        "━━━━━━━━━━━━━━━━━━━━━━"
    ]

    try:
        proc = subprocess.run(
            ["netsh.exe", "wlan", "show", "interfaces"],
            capture_output=True,
            text=True,
            timeout=3.0,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output = proc.stdout

        if proc.returncode != 0 or not output.strip():
            lines.append("⚠️ Wi-Fi subsystem unavailable or no wireless interface found.")
        else:
            state = "Disconnected"
            ssid = "None"
            bssid = "None"
            radio_type = "Unknown"
            signal = "0%"
            channel = "N/A"
            rx_rate = "N/A"
            tx_rate = "N/A"

            for raw_line in output.splitlines():
                line = raw_line.strip()
                if ":" not in line:
                    continue
                k, v = [x.strip() for x in line.split(":", 1)]
                k_lower = k.lower()

                if k_lower == "state":
                    state = v
                elif k_lower == "ssid":
                    ssid = v
                elif k_lower == "bssid":
                    bssid = v
                elif k_lower == "radio type":
                    radio_type = v
                elif k_lower == "signal":
                    signal = v
                elif k_lower == "channel":
                    channel = v
                elif k_lower in ["receive rate (mbps)", "rx rate (mbps)"]:
                    rx_rate = f"{v} Mbps"
                elif k_lower in ["transmit rate (mbps)", "tx rate (mbps)"]:
                    tx_rate = f"{v} Mbps"

            if state.lower() == "connected":
                lines.append(f"🟢 <b>Status:</b> Connected")
                lines.append(f"📡 <b>SSID:</b> <code>{sanitize(ssid)}</code>")
                lines.append(f"📶 <b>Signal Quality:</b> <code>{signal}</code>")
                lines.append(f"📻 <b>Radio Type:</b> {radio_type}")
                lines.append(f"📺 <b>Channel:</b> {channel}")
                lines.append(f"⚡ <b>Link Rate:</b> Rx {rx_rate} / Tx {tx_rate}")
                lines.append(f"🏷️ <b>BSSID:</b> <code>{bssid}</code>")
            else:
                lines.append(f"⚪ <b>Status:</b> {state}")
                lines.append("<i>Wi-Fi adapter is disconnected or offline.</i>")

    except subprocess.TimeoutExpired:
        lines.append("⚠️ Wi-Fi diagnostic timed out (3.0s).")
    except Exception as exc:
        logger.warning(f"execute_wifi error: {sanitize(str(exc))}")
        lines.append(f"❌ Error querying Wi-Fi: {sanitize(str(exc))}")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🔒 <i>Credentials, passwords, and security keys are never queried or exposed.</i>")
    return "\n".join(lines)
