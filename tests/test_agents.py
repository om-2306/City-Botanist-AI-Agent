import os
import sys
import pytest

# Ensure project root is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from agents.vision_agent import run_vision_agent
from agents.location_agent import run_location_agent
from agents.safety_agent import run_safety_agent

def test_run_vision_agent():
    # Test identifying a simulated dandelion
    result = run_vision_agent("simulated_dandelion_image")
    assert "agent_response" in result
    assert "structured_data" in result
    assert result["structured_data"]["plant_name"] == "Dandelion"
    assert result["structured_data"]["scientific_name"] == "Taraxacum officinale"
    assert "Dandelion" in result["agent_response"]

def test_run_location_agent():
    # Test checking a coordinate at Discovery Park (safe)
    lat, lon = 47.6572, -122.4172
    result = run_location_agent(lat, lon)
    assert "agent_response" in result
    assert "structured_data" in result
    assert "pesticide" in result["structured_data"]
    assert "soil" in result["structured_data"]
    assert "weather" in result["structured_data"]
    
    # Discovery Park is clean/safe
    assert result["structured_data"]["pesticide"]["safe_to_forage"] is True
    assert result["structured_data"]["soil"]["safe"] is True

def test_run_safety_agent():
    plant_data = {
        "plant_name": "Stinging Nettle",
        "scientific_name": "Urtica dioica",
        "edible": True,
        "confidence": 0.90,
        "toxicity_warnings": "Stinging hairs cause skin irritation. Cook to neutralize.",
        "lookalikes": ["Dead-nettle"]
    }
    
    # Test safe location data
    safe_location_data = {
        "pesticide": {"sprayed": False, "days_ago": 999, "safe_to_forage": True, "park_name": "Discovery Park"},
        "soil": {"lead_level": 5.2, "safe": True, "contamination_source": "None"},
        "weather": {"temperature": 68.0, "humidity": 55, "recent_rainfall": 0.0, "condition": "Clear"}
    }
    
    result_safe = run_safety_agent(
        plant_data=plant_data,
        location_data=safe_location_data,
        safe_alternatives=[],
        original_lat=47.6572,
        original_lon=-122.4172
    )
    assert result_safe["decision"] == "SAFE TO EAT"
    assert "SAFE TO EAT" in result_safe["agent_response"]

    # Test unsafe location data (recently sprayed)
    unsafe_location_data = {
        "pesticide": {"sprayed": True, "days_ago": 2, "safe_to_forage": False, "park_name": "Volunteer Park"},
        "soil": {"lead_level": 12.4, "safe": True, "contamination_source": "Urban runoff"},
        "weather": {"temperature": 68.0, "humidity": 55, "recent_rainfall": 0.0, "condition": "Clear"}
    }
    
    result_unsafe = run_safety_agent(
        plant_data=plant_data,
        location_data=unsafe_location_data,
        safe_alternatives=[{"park_name": "Seward Park", "distance_km": 5.5, "chemical_status": "No recent", "soil_status": "Safe", "has_plant": "Yes"}],
        original_lat=47.6300,
        original_lon=-122.3150
    )
    assert result_unsafe["decision"] == "DO NOT EAT"
    assert "DO NOT EAT" in result_unsafe["agent_response"]
    assert "Seward Park" in result_unsafe["agent_response"]
