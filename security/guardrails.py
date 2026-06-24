import hashlib
import json
import logging
import os
import re
from datetime import datetime
from typing import Dict, List, Tuple, Union, Optional
from PIL import Image
import io

logger = logging.getLogger("citybotanist.guardrails")

# 1. Location Privacy Protection
def anonymize_location(latitude: float, longitude: float) -> Tuple[float, float]:
    """
    Anonymize GPS coordinates by rounding to 2 decimal places.
    This provides ~1.1km precision (protecting precise user location).
    """
    if latitude is None or longitude is None:
        raise ValueError("Latitude and Longitude cannot be None")
    return round(latitude, 2), round(longitude, 2)

# 2. Plant Misidentification Guardrail
def validate_plant_id_confidence(confidence: float) -> bool:
    """
    Returns True if the confidence is sufficient, False otherwise.
    If confidence is below 80% (0.8), foraging is unsafe.
    """
    return confidence >= 0.8

# 3. Content Safety Filter
def check_safety_claims(text: str) -> Dict[str, Union[bool, str, List[str]]]:
    """
    Scan for absolute or dangerous claims regarding medical benefits or edibility safety.
    Modifies text to add disclaimers and warnings, and flags unsafe text.
    """
    warnings_added = []
    modified_text = text
    
    # Check for absolute medical or safety claims
    absolute_claims = [
        (r"(100%\s*safe|completely\s*safe|totally\s*safe)", "generally considered safe to consume under normal conditions"),
        (r"(cures\s*cancer|cures\s*all\s*diseases|treats\s*all\s*illnesses)", "is traditionally believed to support general wellness"),
        (r"(guaranteed\s*edible|cannot\s*be\s*poisonous)", "is edible but requires correct identification and preparation"),
        (r"(100%\s*sure|perfectly\s*edible)", "is edible subject to habitat conditions")
    ]
    
    for pattern, replacement in absolute_claims:
        if re.search(pattern, modified_text, re.IGNORECASE):
            modified_text = re.sub(pattern, replacement, modified_text, flags=re.IGNORECASE)
            warnings_added.append(f"Replaced absolute claim matching pattern '{pattern}' with a qualified statement.")
            
    # Check if a medical disclaimer is already in the text; if not, append it
    disclaimer = (
        "\n\n[DISCLAIMER: This information is for educational purposes only. "
        "Urban foraging carries risks of misidentification, pesticide exposure, and environmental toxicity. "
        "Always consult with local botanical and agricultural experts before consuming any wild plants.]"
    )
    
    if "educational purposes only" not in modified_text.lower():
        modified_text += disclaimer
        warnings_added.append("Appended standard safety disclaimer.")
        
    return {
        "safe": len(warnings_added) == 0 or "safe" not in text.lower(),
        "modified_text": modified_text,
        "warnings_added": warnings_added
    }

# 4. Input Validation
def validate_gps(latitude: float, longitude: float) -> bool:
    """Validate that GPS coordinates are in valid range."""
    try:
        lat = float(latitude)
        lon = float(longitude)
        return -90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0
    except (ValueError, TypeError):
        return False

def validate_image_file(image_bytes: bytes, filename: str = "uploaded_image") -> Tuple[bool, str]:
    """
    Validate image file size and format.
    Limits to 5MB and supports JPEG, PNG, WEBP.
    """
    # 5MB limit
    MAX_SIZE = 5 * 1024 * 1024
    if len(image_bytes) > MAX_SIZE:
        return False, "Image size exceeds 5MB limit"
        
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img_format = img.format.upper() if img.format else ""
        if img_format not in ["JPEG", "PNG", "WEBP", "JPG"]:
            return False, f"Unsupported image format: {img_format}. Use JPEG, PNG, or WEBP."
        return True, "Valid"
    except Exception as e:
        return False, f"Invalid image file: {str(e)}"

def sanitize_input(text: str) -> str:
    """
    Sanitize text input against prompt injection or malicious code.
    Removes HTML tags and strips potential system override instructions.
    """
    if not text:
        return ""
    # Strip HTML tags
    cleaned = re.sub(r"<[^>]*>", "", text)
    # Block common prompt injection phrases
    injection_phrases = [
        "ignore previous instructions",
        "system override",
        "you are now a",
        "forget what you were told"
    ]
    for phrase in injection_phrases:
        if phrase in cleaned.lower():
            cleaned = re.sub(re.escape(phrase), "[REDACTED INJECTION ATTEMPT]", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()

# 5. Audit Logging
def log_audit_transaction(
    latitude: float,
    longitude: float,
    plant_identified: str,
    safety_decision: str,
    reasoning: str,
    tool_calls: Optional[List[Dict]] = None,
    log_file: str = "audit_log.json"
) -> str:
    """
    Log all agent decisions with timestamps and save to a JSON audit log file.
    Uses SHA-256 hash of coordinates to maintain location privacy.
    Returns the hashed coordinates.
    """
    # Hash coordinates to protect privacy
    coord_string = f"{latitude},{longitude}"
    user_location_hash = hashlib.sha256(coord_string.encode('utf-8')).hexdigest()
    
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "user_location_hash": user_location_hash,
        "plant_identified": plant_identified,
        "safety_decision": safety_decision,
        "reasoning": reasoning,
        "tool_calls": tool_calls or []
    }
    
    try:
        # Load existing logs
        logs = []
        if os.path.exists(log_file):
            try:
                with open(log_file, "r") as f:
                    logs = json.load(f)
                    if not isinstance(logs, list):
                        logs = []
            except json.JSONDecodeError:
                # Corrupted log file
                logs = []
                
        logs.append(log_entry)
        
        # Save updated logs
        with open(log_file, "w") as f:
            json.dump(logs, f, indent=2)
            
    except Exception as e:
        logger.error(f"Failed to write to audit log: {e}")
        
    return user_location_hash
