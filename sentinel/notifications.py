import html
from datetime import datetime
from typing import Dict, Any

def format_telegram_alert(event_type: str, system_info: Dict[str, Any], network_info: Dict[str, Any]) -> str:
    """
    Builds a beautifully structured HTML-formatted Telegram message.
    """
    is_startup = event_type.lower() == "startup"
    icon = "🚀" if is_startup else "🛑"
    header_title = "SYSTEM STARTUP" if is_startup else "SYSTEM SHUTDOWN"
    status_line = "✅ <b>Status:</b> Event triggered and confirmed" if is_startup else "⚡ <b>Status:</b> Shutdown initiated"

    timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    device = html.escape(str(system_info.get("device", "ASUS TUF A15")))
    os_name = html.escape(str(system_info.get("os", "Windows 11")))
    user = html.escape(str(system_info.get("user", "User")))

    battery = html.escape(str(system_info.get("battery_percent", "Unavailable")))
    power = html.escape(str(system_info.get("power_source", "Unavailable")))

    ip = html.escape(str(network_info.get("ip", "Unavailable")))
    location = html.escape(str(network_info.get("location", "Unavailable")))
    lat = network_info.get("latitude")
    lon = network_info.get("longitude")
    maps_url = network_info.get("maps_url")

    # Build sections
    lines = [
        f"{icon} <b>SENTINEL ALERT — {header_title}</b>\n",
        "━━━━━━━━━━━━━━━━━━━━━━\n",
        f"💻 <b>Device:</b> {device}",
        f"🪟 <b>OS:</b> {os_name}",
        f"👤 <b>User:</b> {user}",
        f"🕒 <b>Time:</b> {timestamp}\n",
        f"🔋 <b>Battery:</b> {battery}",
        f"⚡ <b>Power:</b> {power}\n",
        f"🌐 <b>Public IP:</b> {ip}"
    ]

    # Location section
    if location != "Unavailable":
        lines.append(f"\n📍 <b>Approximate Location:</b>\n{location}")
        if lat is not None and lon is not None:
            lines.append(f"\n🧭 <b>Coordinates:</b>\n{lat:.5f}, {lon:.5f}")
        if maps_url:
            lines.append(f"\n🗺️ <b>Map:</b>\n{maps_url}")
    else:
        lines.append(f"\n📍 <b>Approximate Location:</b> Unavailable")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(status_line)

    return "\n".join(lines)
