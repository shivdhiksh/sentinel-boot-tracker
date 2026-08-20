import html
from datetime import datetime
from typing import Dict, Any

EVENT_METADATA = {
    "startup": {
        "icon": "🚀",
        "title": "SYSTEM STARTUP",
        "status": "✅ <b>Status:</b> Event triggered and confirmed"
    },
    "shutdown": {
        "icon": "🛑",
        "title": "SYSTEM SHUTDOWN",
        "status": "⚡ <b>Status:</b> Shutdown initiated"
    },
    "lock": {
        "icon": "🔒",
        "title": "WORKSTATION LOCKED",
        "status": "🔒 <b>Status:</b> Workstation locked"
    },
    "unlock": {
        "icon": "🔓",
        "title": "WORKSTATION UNLOCKED",
        "status": "🔓 <b>Status:</b> Workstation unlocked"
    }
}

def format_telegram_alert(
    event_type: str,
    system_info: Dict[str, Any],
    network_info: Dict[str, Any],
    location_telemetry: Dict[str, Any]
) -> str:
    """
    Builds a beautifully structured HTML-formatted Telegram message
    with support for all power/session events and multi-tier location rendering.
    """
    ev_meta = EVENT_METADATA.get(event_type.lower(), EVENT_METADATA["startup"])
    icon = ev_meta["icon"]
    header_title = ev_meta["title"]
    status_line = ev_meta["status"]

    timestamp = datetime.now().strftime("%Y-%m-%d %I:%M:%S %p")
    device = html.escape(str(system_info.get("device", "ASUS TUF A15")))
    os_name = html.escape(str(system_info.get("os", "Windows 11")))
    user = html.escape(str(system_info.get("user", "User")))

    battery = html.escape(str(system_info.get("battery_percent", "Unavailable")))
    power = html.escape(str(system_info.get("power_source", "Unavailable")))
    ip = html.escape(str(network_info.get("ip", "Unavailable")))

    # Base message sections
    lines = [
        f"{icon} <b>SENTINEL ALERT — {header_title}</b>\n",
        "━━━━━━━━━━━━━━━━━━━━━━\n",
        f"💻 <b>Device:</b> {device}",
        f"🪟 <b>OS:</b> {os_name}",
        f"👤 <b>User:</b> {user}",
        f"🕒 <b>Time:</b> {timestamp}\n",
        f"🔋 <b>Battery:</b> {battery}",
        f"⚡ <b>Power:</b> {power}\n",
        f"🌐 <b>Public IP:</b> {ip}\n"
    ]

    tier = location_telemetry.get("location_tier", "ip_fallback")
    lat = location_telemetry.get("latitude")
    lon = location_telemetry.get("longitude")
    maps_url = location_telemetry.get("maps_url")
    source = html.escape(str(location_telemetry.get("source", "Unknown")))
    accuracy_m = location_telemetry.get("accuracy_meters")
    age_str = html.escape(str(location_telemetry.get("age_string", "live")))

    if tier == "windows_live":
        acc_display = f"~{int(round(accuracy_m))} m" if accuracy_m is not None else "High"
        lines.append("📍 <b>LOCATION</b>")
        if lat is not None and lon is not None:
            lines.append(f"Latitude: {lat:.6f}")
            lines.append(f"Longitude: {lon:.6f}\n")
        lines.append(f"🎯 <b>Accuracy:</b> {acc_display}")
        lines.append(f"📡 <b>Source:</b> {source}")
        lines.append("🟢 <b>Status:</b> Live location")
        if maps_url:
            lines.append(f"\n🗺️ <b>Google Maps:</b>\n{maps_url}")

    elif tier == "cached":
        acc_display = f"~{int(round(accuracy_m))} m" if accuracy_m is not None else "High"
        lines.append("📍 <b>LOCATION</b>")
        if lat is not None and lon is not None:
            lines.append(f"Latitude: {lat:.6f}")
            lines.append(f"Longitude: {lon:.6f}\n")
        lines.append(f"🎯 <b>Accuracy:</b> {acc_display}")
        lines.append(f"📡 <b>Source:</b> {source}")
        lines.append(f"🕒 <b>Location updated:</b> {age_str}")
        lines.append("🟡 <b>Status:</b> Cached location")
        if maps_url:
            lines.append(f"\n🗺️ <b>Google Maps:</b>\n{maps_url}")

    else:  # ip_fallback
        loc_name = html.escape(str(location_telemetry.get("location_name", "Unavailable")))
        lines.append("📍 <b>APPROXIMATE LOCATION</b>")
        lines.append(f"{loc_name}\n")
        lines.append("🎯 <b>Accuracy:</b> Approximate")
        lines.append(f"📡 <b>Source:</b> {source}")
        lines.append("⚠️ <i>IP-based location is not precise.</i>")
        if maps_url:
            lines.append(f"\n🗺️ <b>Google Maps:</b>\n{maps_url}")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(status_line)

    return "\n".join(lines)
