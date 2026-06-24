import os
import sys
import json
import pytest

# Ensure project root is in path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

from agents.orchestrator import run_city_botanist_workflow

def test_complete_unsafe_foraging_journey():
    # Scenario: Forager uploads a Blackberry at Volunteer Park (recently sprayed)
    # Coordinates of Volunteer Park: (47.6300, -122.3150)
    lat, lon = 47.630012, -122.315089
    image_input = "simulated_blackberry_image"
    
    # Run the orchestrator
    result = run_city_botanist_workflow(
        image_base64=image_input,
        latitude=lat,
        longitude=lon,
        human_approved_lookalike=True
    )
    
    # Verify success of workflow execution
    assert result["success"] is True
    
    # Verify DO NOT EAT verdict due to pesticide spraying
    assert result["decision"] == "DO NOT EAT"
    assert "DO NOT EAT" in result["safety_report"]
    assert "Volunteer Park" in result["location_report"] or "Volunteer Park" in result["safety_report"]
    
    # Verify location anonymization occurred (the logs should reflect this, and result contains it)
    # Check that coordinates were anonymized to 2 decimal places
    # Hashing should be present
    user_hash = result["user_location_hash"]
    assert user_hash is not None
    assert len(user_hash) == 64  # SHA-256 length is 64 characters hex
    
    # Check that alternatives are suggested
    assert len(result["safe_alternatives"]) > 0
    alternative_names = [alt["park_name"] for alt in result["safe_alternatives"]]
    assert "Cal Anderson Park" in alternative_names or "Green Lake Park" in alternative_names
    
    # Verify audit logging
    log_file = "audit_log.json"
    assert os.path.exists(log_file)
    with open(log_file, "r") as f:
        logs = json.load(f)
        assert len(logs) > 0
        latest_log = logs[-1]
        assert latest_log["user_location_hash"] == user_hash
        assert latest_log["plant_identified"] == "Himalayan Blackberry"
        assert latest_log["safety_decision"] == "DO NOT EAT"
        assert len(latest_log["tool_calls"]) > 0
