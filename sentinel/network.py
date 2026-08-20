import requests
from typing import Dict, Any, Optional
from .config import logger, sanitize

def get_network_info(timeout: float = 3.5) -> Dict[str, Any]:
    """
    Fetches public IP and approximate IP-based geolocation.
    
    IMPORTANT:
    - This is approximate IP geolocation, NOT GPS.
    - Fails gracefully without throwing exceptions.
    - Multi-provider fallback strategy (ipapi.co -> ip-api.com -> ipify.org).
    """
    result: Dict[str, Any] = {
        "ip": "Unavailable",
        "location": "Unavailable",
        "latitude": None,
        "longitude": None,
        "maps_url": None
    }

    # Provider 1: ipapi.co
    try:
        headers = {"User-Agent": "sentinel-boot-tracker/0.3"}
        resp = requests.get("https://ipapi.co/json/", headers=headers, timeout=timeout)
        if resp.ok:
            data = resp.json()
            ip = data.get("ip")
            city = data.get("city")
            region = data.get("region")
            country = data.get("country_name")
            lat = data.get("latitude")
            lon = data.get("longitude")

            if ip:
                result["ip"] = str(ip)

            loc_parts = [p for p in [city, region, country] if p]
            if loc_parts:
                result["location"] = ", ".join(loc_parts)

            if lat is not None and lon is not None:
                try:
                    lat_f = float(lat)
                    lon_f = float(lon)
                    result["latitude"] = lat_f
                    result["longitude"] = lon_f
                    result["maps_url"] = f"https://www.google.com/maps?q={lat_f},{lon_f}"
                except (ValueError, TypeError):
                    pass

            return result
    except Exception as exc:
        logger.warning(f"Primary IP provider (ipapi.co) failed: {sanitize(str(exc))}")

    # Provider 2: ip-api.com
    try:
        resp = requests.get("http://ip-api.com/json/", timeout=timeout)
        if resp.ok:
            data = resp.json()
            if data.get("status") == "success":
                ip = data.get("query")
                city = data.get("city")
                region = data.get("regionName")
                country = data.get("country")
                lat = data.get("lat")
                lon = data.get("lon")

                if ip:
                    result["ip"] = str(ip)

                loc_parts = [p for p in [city, region, country] if p]
                if loc_parts:
                    result["location"] = ", ".join(loc_parts)

                if lat is not None and lon is not None:
                    try:
                        lat_f = float(lat)
                        lon_f = float(lon)
                        result["latitude"] = lat_f
                        result["longitude"] = lon_f
                        result["maps_url"] = f"https://www.google.com/maps?q={lat_f},{lon_f}"
                    except (ValueError, TypeError):
                        pass

                return result
    except Exception as exc:
        logger.warning(f"Secondary IP provider (ip-api.com) failed: {sanitize(str(exc))}")

    # Provider 3: ipify.org (IP only fallback)
    try:
        resp = requests.get("https://api.ipify.org?format=json", timeout=timeout)
        if resp.ok:
            data = resp.json()
            ip = data.get("ip")
            if ip:
                result["ip"] = str(ip)
    except Exception as exc:
        logger.warning(f"Tertiary IP provider (ipify.org) failed: {sanitize(str(exc))}")

    return result
