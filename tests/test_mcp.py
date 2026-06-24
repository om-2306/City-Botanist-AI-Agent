import os
import sys
import pytest

# Ensure project root is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from agents.orchestrator import call_mcp_tool_directly

def test_plant_id_mcp_tools():
    # Test plant details lookup
    details = call_mcp_tool_directly("plant_id_mcp.py", "get_plant_details", {"plant_name": "Dandelion"})
    assert details["name"] == "Dandelion"
    assert details["scientific_name"] == "Taraxacum officinale"
    assert details["edible"] is True
    
    # Test detail lookup fallback
    missing_details = call_mcp_tool_directly("plant_id_mcp.py", "get_plant_details", {"plant_name": "Unknown Cactus"})
    assert "not found" in missing_details["error"]
    assert missing_details["edible"] is False

    # Test plant identification simulated keyword extraction
    ident_dandelion = call_mcp_tool_directly("plant_id_mcp.py", "identify_plant", {"image_base64": "simulated_dandelion_image"})
    assert ident_dandelion["plant_name"] == "Dandelion"
    assert ident_dandelion["confidence"] == 0.95
    assert ident_dandelion["edible"] is True
    
    ident_hemlock = call_mcp_tool_directly("plant_id_mcp.py", "identify_plant", {"image_base64": "simulated_hemlock_image"})
    assert ident_hemlock["plant_name"] == "Poison Hemlock"
    assert ident_hemlock["edible"] is False

def test_city_data_mcp_tools():
    # Test pesticide spraying check on sprayed park (Volunteer Park)
    vol_park_lat, vol_park_lon = 47.6300, -122.3150
    spraying_report = call_mcp_tool_directly(
        "city_data_mcp.py", 
        "check_pesticide_spraying", 
        {"latitude": vol_park_lat, "longitude": vol_park_lon}
    )
    assert spraying_report["park_name"] == "Volunteer Park"
    assert spraying_report["sprayed"] is True
    assert spraying_report["safe_to_forage"] is False
    assert spraying_report["chemical"] == "Glyphosate"

    # Test pesticide spraying check on safe park (Discovery Park)
    disc_park_lat, disc_park_lon = 47.6572, -122.4172
    spraying_report_safe = call_mcp_tool_directly(
        "city_data_mcp.py", 
        "check_pesticide_spraying", 
        {"latitude": disc_park_lat, "longitude": disc_park_lon}
    )
    assert spraying_report_safe["park_name"] == "Discovery Park"
    assert spraying_report_safe["sprayed"] is False
    assert spraying_report_safe["safe_to_forage"] is True

    # Test soil contamination check on toxic park (Gas Works Park)
    gw_park_lat, gw_park_lon = 47.6456, -122.3344
    soil_report = call_mcp_tool_directly(
        "city_data_mcp.py", 
        "get_soil_contamination", 
        {"latitude": gw_park_lat, "longitude": gw_park_lon}
    )
    assert soil_report["park_name"] == "Gas Works Park"
    assert soil_report["safe"] is False
    assert soil_report["lead_level"] > 80.0
    
    # Test find safe alternatives
    alternatives = call_mcp_tool_directly(
        "city_data_mcp.py", 
        "find_safe_alternatives", 
        {"latitude": vol_park_lat, "longitude": vol_park_lon, "plant_name": "Wild Garlic"}
    )
    assert len(alternatives) > 0
    # Alternatives returned must be safe
    for alt in alternatives:
        assert "Safe" in alt["soil_status"]
        assert "Safe" in alt["chemical_status"] or "No recent" in alt["chemical_status"]

def test_weather_mcp_tools():
    # Test weather lookup
    weather = call_mcp_tool_directly("weather_mcp.py", "get_weather", {"latitude": 47.6572, "longitude": -122.4172})
    assert "temperature" in weather
    assert "humidity" in weather
    assert "condition" in weather
    assert "source" in weather
