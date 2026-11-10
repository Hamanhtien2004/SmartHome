#!/usr/bin/env python3
"""
Weather Service for Smart Home AI Agent
---------------------------------------
Fetches real-time weather and forecast using Open-Meteo API (Free, No API key required).
Translates weather codes to natural Vietnamese descriptions and advice.
"""

import urllib.request
import json
import logging
from typing import Dict, Any

logger = logging.getLogger("SmartHomeWeather")

# Default coordinates: Hanoi, Vietnam (21.0285, 105.8542)
DEFAULT_LAT = 21.0285
DEFAULT_LON = 105.8542

# WMO Weather interpretation codes
WMO_CODES_VI = {
    0: "Trời quang đãng, nắng đẹp",
    1: "Chủ yếu trời quang, ít mây",
    2: "Trời có mây rải rác",
    3: "Trời nhiều mây u ám",
    45: "Có sương mù",
    48: "Sương mù đóng băng",
    51: "Mưa phùn nhẹ",
    53: "Mưa phùn vừa",
    55: "Mưa phùn dày hạt",
    61: "Mưa rào nhẹ",
    63: "Mưa rào vừa",
    65: "Mưa rào nặng hạt",
    71: "Tuyết rơi nhẹ",
    80: "Mưa rào ngắt quãng",
    81: "Mưa rào xối xả",
    82: "Mưa rất to",
    95: "Có dông sét",
    96: "Dông sét kèm mưa đá nhỏ",
    99: "Dông sét kèm mưa đá dữ dội"
}

def get_current_weather(lat: float = DEFAULT_LAT, lon: float = DEFAULT_LON) -> Dict[str, Any]:
    """Fetch current outdoor weather and daily forecast."""
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,"
        f"apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m&"
        f"daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&"
        f"timezone=Asia%2FBangkok"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SmartHomeAIAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        current = data.get("current", {})
        daily = data.get("daily", {})

        weather_code = current.get("weather_code", 0)
        desc = WMO_CODES_VI.get(weather_code, "Thời tiết bình thường")

        temp = current.get("temperature_2m", 26.0)
        feel_temp = current.get("apparent_temperature", temp)
        humidity = current.get("relative_humidity_2m", 65)
        wind = current.get("wind_speed_10m", 5.0)
        precip = current.get("precipitation", 0.0)

        # Daily extremes
        max_temp = daily.get("temperature_2m_max", [temp])[0] if daily.get("temperature_2m_max") else temp
        min_temp = daily.get("temperature_2m_min", [temp])[0] if daily.get("temperature_2m_min") else temp
        rain_prob = daily.get("precipitation_probability_max", [0])[0] if daily.get("precipitation_probability_max") else 0

        # Smart advice
        advice = []
        if rain_prob > 50 or precip > 0 or weather_code in [51, 53, 55, 61, 63, 65, 80, 81, 82, 95]:
            advice.append("Khả năng có mưa cao, bạn nhớ mang theo ô hoặc áo mưa khi ra ngoài và đóng cửa sổ phòng nhé.")
        if temp > 33:
            advice.append("Thời tiết bên ngoài rất nóng, bạn nên uống nhiều nước và tránh ra đường lúc trưa gắt.")
        elif temp < 18:
            advice.append("Trời trở lạnh, bạn nên mặc thêm áo ấm khi ra khỏi nhà.")

        if not advice:
            advice.append("Thời tiết ngoài trời hôm nay khá thuận lợi cho các hoạt động ngoài trời.")

        return {
            "success": True,
            "temperature": temp,
            "apparent_temperature": feel_temp,
            "humidity": humidity,
            "wind_speed": wind,
            "weather_code": weather_code,
            "description": desc,
            "temp_max": max_temp,
            "temp_min": min_temp,
            "rain_probability": rain_prob,
            "advice": " ".join(advice)
        }
    except Exception as exc:
        logger.warning("Could not fetch online weather: %s. Using fallback defaults.", exc)
        return {
            "success": False,
            "temperature": 27.5,
            "apparent_temperature": 29.0,
            "humidity": 70,
            "wind_speed": 8.0,
            "weather_code": 1,
            "description": "Trời có mây nhẹ rải rác",
            "temp_max": 31.0,
            "temp_min": 24.0,
            "rain_probability": 20,
            "advice": "Thời tiết hôm nay dễ chịu, thích hợp cho mọi sinh hoạt gia đình."
        }

if __name__ == "__main__":
    w = get_current_weather()
    print("Weather result:", json.dumps(w, indent=2, ensure_ascii=False))
