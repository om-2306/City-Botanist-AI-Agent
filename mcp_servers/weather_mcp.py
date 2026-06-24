import os
import requests
import logging
from typing import Dict, Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("weather_mcp")

# Initialize FastMCP Server
mcp = FastMCP("Weather MCP Server")

# Mapping of WMO weather codes to human-readable strings
# Reference: WMO weather interpretation codes (https://open-meteo.com/en/docs)
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow fall", 73: "Moderate snow fall", 75: "Heavy snow fall",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    95: "Thunderstorm", 96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail"
}

@mcp.tool()
def get_weather(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Get current weather conditions at specified coordinates.
    Retrieves real-time data from Open-Meteo or falls back to mock data if offline.
    
    Args:
        latitude: Latitude coordinate.
        longitude: Longitude coordinate.
    """
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={latitude}&longitude={longitude}"
        f"&current=temperature_2m,relative_humidity_2m,rain,weather_code"
    )
    
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            current = data.get("current", {})
            temp = current.get("temperature_2m", 65.0)
            humidity = current.get("relative_humidity_2m", 50.0)
            rain = current.get("rain", 0.0)
            code = current.get("weather_code", 0)
            condition = WEATHER_CODES.get(code, "Clear")
            
            return {
                "temperature": temp,
                "humidity": humidity,
                "recent_rainfall": rain,
                "condition": condition,
                "source": "Open-Meteo API"
            }
    except Exception as e:
        logger.error(f"Weather API call failed: {e}. Using mock weather.")
        
    # Return mock data as a robust fallback
    # We can vary the weather slightly based on coordinates to make it look dynamic
    is_rainy = (int(latitude * 10) + int(longitude * 10)) % 3 == 0
    return {
        "temperature": round(60.0 + (latitude % 5) * 2, 1),
        "humidity": 85 if is_rainy else 55,
        "recent_rainfall": 0.4 if is_rainy else 0.0,
        "condition": "Light rain showers" if is_rainy else "Partly cloudy",
        "source": "Local Mock Weather Service"
    }

if __name__ == "__main__":
    mcp.run()
