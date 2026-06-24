import os
import json
import pytest
from security import guardrails

def test_location_anonymization():
    # Test rounding to 2 decimal places
    lat, lon = 47.617412, -122.319589
    anon_lat, anon_lon = guardrails.anonymize_location(lat, lon)
    assert anon_lat == 47.62
    assert anon_lon == -122.32
    
    lat2, lon2 = 47.1, -122.9
    anon_lat2, anon_lon2 = guardrails.anonymize_location(lat2, lon2)
    assert anon_lat2 == 47.10
    assert anon_lon2 == -122.90

def test_plant_id_confidence_guardrail():
    # Confidence below 0.8 should fail validation
    assert not guardrails.validate_plant_id_confidence(0.79)
    assert not guardrails.validate_plant_id_confidence(0.50)
    
    # Confidence >= 0.8 should pass
    assert guardrails.validate_plant_id_confidence(0.80)
    assert guardrails.validate_plant_id_confidence(0.95)

def test_content_safety_filter():
    # Test replacement of absolute claims
    claim_text = "This plant is 100% safe and cures cancer immediately!"
    result = guardrails.check_safety_claims(claim_text)
    
    assert not result["safe"]
    assert "100% safe" not in result["modified_text"]
    assert "cures cancer" not in result["modified_text"]
    assert "educational purposes only" in result["modified_text"]
    assert len(result["warnings_added"]) > 0

    # Test clean text already containing disclaimer
    clean_text = "Dandelions are commonly eaten. [DISCLAIMER: This information is for educational purposes only.]"
    result_clean = guardrails.check_safety_claims(clean_text)
    assert result_clean["safe"]
    assert "educational purposes only" in result_clean["modified_text"]

def test_gps_validation():
    # Valid coordinates
    assert guardrails.validate_gps(47.6174, -122.3195)
    assert guardrails.validate_gps(0.0, 0.0)
    assert guardrails.validate_gps(90.0, 180.0)
    assert guardrails.validate_gps(-90.0, -180.0)
    
    # Invalid coordinates
    assert not guardrails.validate_gps(91.0, -122.3)
    assert not guardrails.validate_gps(47.6, 181.0)
    assert not guardrails.validate_gps("invalid", -122.3)

def test_image_validation():
    # Test valid small mock JPEG/PNG header bytes
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    # Note: PIL might throw an exception on truncated file content, but let's test it raises/catches
    # Let's create actual tiny images in memory for testing
    from PIL import Image
    import io
    
    img = Image.new('RGB', (100, 100), color = 'red')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    valid_bytes = img_byte_arr.getvalue()
    
    is_valid, msg = guardrails.validate_image_file(valid_bytes)
    assert is_valid
    assert msg == "Valid"
    
    # Test too large file
    huge_bytes = b"0" * (5 * 1024 * 1024 + 1)
    is_valid_huge, msg_huge = guardrails.validate_image_file(huge_bytes)
    assert not is_valid_huge
    assert "size" in msg_huge.lower()

def test_audit_logging():
    log_file = "test_audit_log.json"
    if os.path.exists(log_file):
        os.remove(log_file)
        
    try:
        user_hash = guardrails.log_audit_transaction(
            latitude=47.63,
            longitude=-122.31,
            plant_identified="Stinging Nettle",
            safety_decision="SAFE TO EAT",
            reasoning="Pesticides and soil levels are clear.",
            log_file=log_file
        )
        
        # Verify file creation
        assert os.path.exists(log_file)
        
        # Verify contents
        with open(log_file, "r") as f:
            logs = json.load(f)
            assert len(logs) == 1
            assert logs[0]["plant_identified"] == "Stinging Nettle"
            assert logs[0]["user_location_hash"] == user_hash
            assert logs[0]["safety_decision"] == "SAFE TO EAT"
            
    finally:
        if os.path.exists(log_file):
            os.remove(log_file)
