"""
Multi-Tier Geolocation Engine:
Tier 1: Windows.Devices.Geolocation (WinRT Native Geolocation API - Active User Session)
Tier 2: User-Session Location Cache (.location_cache.json with 1-hour freshness validation)
Tier 3: IP Geolocation Fallback (ipapi.co / ip-api.com / ipify.org)
"""
import os
import json
import time
import asyncio
import getpass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional

from .config import BASE_DIR, logger, sanitize
from .network import get_network_info

CACHE_FILE = BASE_DIR / ".location_cache.json"
MAX_CACHE_AGE_SECONDS = 3600  # 1 hour strict freshness threshold

POSITION_SOURCE_MAP = {
    0: "Cellular",
    1: "Satellite/GNSS",
    2: "Wi-Fi",
    3: "IP address",
    4: "Unknown",
    5: "Default",
    6: "Obfuscated"
}

def is_system_context() -> bool:
    """Detects if running under NT AUTHORITY\\SYSTEM in Session 0."""
    try:
        user = getpass.getuser().upper()
        return "SYSTEM" in user or os.getenv("USERNAME", "").upper() == "SYSTEM"
    except Exception:
        return False

def calculate_age_string(timestamp_iso: str) -> tuple[str, bool]:
    """Calculates human-readable age string and freshness flag (< 1 hour)."""
    try:
        ts = datetime.fromisoformat(timestamp_iso)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff_seconds = max(0, int((now - ts).total_seconds()))
        
        is_stale = diff_seconds > MAX_CACHE_AGE_SECONDS
        
        if diff_seconds < 60:
            return "just now", is_stale
        elif diff_seconds < 3600:
            mins = diff_seconds // 60
            return f"{mins} minute{'s' if mins > 1 else ''} ago", is_stale
        elif diff_seconds < 86400:
            hrs = diff_seconds // 3600
            return f"{hrs} hour{'s' if hrs > 1 else ''} ago", is_stale
        else:
            days = diff_seconds // 86400
            return f"{days} day{'s' if days > 1 else ''} ago", is_stale
    except Exception:
        return "previously", True

def load_location_cache() -> Optional[Dict[str, Any]]:
    """Loads location cache and verifies integrity and freshness."""
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not all(k in data for k in ["latitude", "longitude", "accuracy_meters", "source", "timestamp"]):
            return None
        
        age_str, is_stale = calculate_age_string(data["timestamp"])
        data["age_string"] = age_str
        data["is_stale"] = is_stale
        return data
    except Exception as exc:
        logger.warning(f"Failed to read location cache: {sanitize(str(exc))}")
        return None

def save_location_cache(lat: float, lon: float, accuracy: float, source: str) -> None:
    """Saves minimum necessary location data to local cache."""
    try:
        cache_data = {
            "latitude": float(lat),
            "longitude": float(lon),
            "accuracy_meters": float(accuracy),
            "source": source,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
    except Exception as exc:
        logger.warning(f"Failed to write location cache: {sanitize(str(exc))}")

async def _query_windows_location_async(timeout: float = 3.5) -> Optional[Dict[str, Any]]:
    """Direct query to Windows.Devices.Geolocation with timeout."""
    try:
        from winrt.windows.devices.geolocation import (
            Geolocator,
            GeolocationAccessStatus,
            PositionAccuracy
        )
        
        # Check permissions
        access = await Geolocator.request_access_async()
        if access != GeolocationAccessStatus.ALLOWED:
            logger.info("Windows location access denied or unspecified.")
            return None
            
        geolocator = Geolocator()
        geolocator.desired_accuracy = PositionAccuracy.HIGH
        
        pos = await asyncio.wait_for(geolocator.get_geoposition_async(), timeout=timeout)
        coord = pos.coordinate
        point = coord.point.position
        
        lat = float(point.latitude)
        lon = float(point.longitude)
        accuracy = float(coord.accuracy) if coord.accuracy is not None else 0.0
        raw_source = getattr(coord, "position_source", 4)
        source_val = int(raw_source) if hasattr(raw_source, "value") else int(raw_source)
        source_name = POSITION_SOURCE_MAP.get(source_val, "Unknown")
        
        return {
            "latitude": lat,
            "longitude": lon,
            "accuracy_meters": accuracy,
            "source": source_name,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as exc:
        logger.info(f"Windows native location query skipped/failed: {sanitize(str(exc))}")
        return None

def get_windows_location(timeout: float = 3.5) -> Optional[Dict[str, Any]]:
    """Synchronous wrapper for Windows native location query."""
    try:
        return asyncio.run(_query_windows_location_async(timeout=timeout))
    except Exception as exc:
        logger.info(f"Asyncio runner for Windows location failed: {sanitize(str(exc))}")
        return None

def get_location_telemetry(timeout: float = 3.5, force_ip: bool = False, force_system_mode: bool = False) -> Dict[str, Any]:
    """
    Multi-tier location resolver:
    Tier 1: Windows.Devices.Geolocation (active user session only)
    Tier 2: Fresh local location cache (< 1 hour old, for SYSTEM shutdown / offline)
    Tier 3: IP Geolocation fallback
    """
    is_sys = force_system_mode or is_system_context()

    # Tier 1: Live Windows Location (only if NOT running in SYSTEM context and not force_ip)
    if not is_sys and not force_ip:
        win_loc = get_windows_location(timeout=timeout)
        if win_loc is not None:
            save_location_cache(
                win_loc["latitude"],
                win_loc["longitude"],
                win_loc["accuracy_meters"],
                win_loc["source"]
            )
            return {
                "location_tier": "windows_live",
                "latitude": win_loc["latitude"],
                "longitude": win_loc["longitude"],
                "accuracy_meters": win_loc["accuracy_meters"],
                "source": win_loc["source"],
                "maps_url": f"https://www.google.com/maps?q={win_loc['latitude']},{win_loc['longitude']}",
                "timestamp": win_loc["timestamp"],
                "age_string": "live",
                "status": "Live location"
            }

    # Tier 2: Cached Location (only if fresh < 1 hour and not force_ip)
    if not force_ip:
        cached = load_location_cache()
        if cached is not None and not cached.get("is_stale", True):
            return {
                "location_tier": "cached",
                "latitude": cached["latitude"],
                "longitude": cached["longitude"],
                "accuracy_meters": cached["accuracy_meters"],
                "source": cached["source"],
                "maps_url": f"https://www.google.com/maps?q={cached['latitude']},{cached['longitude']}",
                "timestamp": cached["timestamp"],
                "age_string": cached["age_string"],
                "status": "Cached location"
            }

    # Tier 3: IP Geolocation Fallback
    ip_net = get_network_info(timeout=timeout)
    return {
        "location_tier": "ip_fallback",
        "location_name": ip_net.get("location", "Unavailable"),
        "latitude": ip_net.get("latitude"),
        "longitude": ip_net.get("longitude"),
        "accuracy_meters": None,
        "source": "IP address",
        "maps_url": ip_net.get("maps_url"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "age_string": "live",
        "status": "Approximate location"
    }

if __name__ == "__main__":
    print("=" * 50)
    print("SENTINEL LOCATION TELEMETRY TEST (STANDALONE)")
    print("=" * 50)
    loc = get_location_telemetry()
    tier_label = loc.get("location_tier", "unknown")
    print(f"Location Tier:   {tier_label.upper()}")
    print(f"Latitude:        {loc.get('latitude')}")
    print(f"Longitude:       {loc.get('longitude')}")
    if loc.get("accuracy_meters") is not None:
        print(f"Accuracy:        ~{int(round(loc['accuracy_meters']))} m")
    else:
        print(f"Accuracy:        Approximate")
    print(f"Position Source: {loc.get('source')}")
    print(f"Status:          {loc.get('status')}")
    print(f"Timestamp / Age: {loc.get('timestamp')} ({loc.get('age_string')})")
    print(f"Cache File:      {'Exists (' + str(CACHE_FILE) + ')' if CACHE_FILE.exists() else 'None'}")
    print(f"Google Maps URL: {loc.get('maps_url')}")
    print("=" * 50)
