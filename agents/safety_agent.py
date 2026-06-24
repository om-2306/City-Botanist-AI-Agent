import os
import json
import logging
from typing import Dict, Any, List

try:
    from google.adk.agents.llm_agent import Agent
    from google.adk.runners import InMemoryRunner
    HAS_ADK = True
except ImportError:
    HAS_ADK = False

logger = logging.getLogger("citybotanist.safety_agent")

SYSTEM_INSTRUCTION = (
    "You are a food safety expert specializing in urban foraging. "
    "Given the plant identification and location safety data, make a definitive recommendation "
    "on whether this plant is safe to consume. "
    "Consider the following criteria:\n"
    "1. Is the plant itself edible? (If inedible/toxic, recommendation is DO NOT EAT)\n"
    "2. Was the location sprayed with pesticides in the last 14 days? (If sprayed, recommendation is DO NOT EAT)\n"
    "3. Is there heavy metal soil contamination (lead levels > 80 ppm)? (If contaminated, recommendation is DO NOT EAT)\n"
    "4. Is the identification confidence score below 80%? (If confidence < 0.8, recommendation is DO NOT EAT)\n\n"
    "If ANY risk factor is present, you must write 'DECISION: DO NOT EAT' in bold uppercase text. "
    "If all factors are safe, you must write 'DECISION: SAFE TO EAT' in bold uppercase text. "
    "Explain your reasoning clearly, detailing each risk factor. "
    "If the decision is DO NOT EAT and safe alternatives are provided, list them as safer places to forage for this plant."
)

def run_safety_agent(
    plant_data: Dict[str, Any],
    location_data: Dict[str, Any],
    safe_alternatives: List[Dict[str, Any]],
    original_lat: float,
    original_lon: float
) -> Dict[str, Any]:
    """
    Run the Safety Agent to synthesize plant and location data and make a final recommendation.
    Uses Google ADK if API keys are available, otherwise runs a high-fidelity mock fallback.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    
    # Construct the input prompt for synthesis
    prompt = (
        f"PLANT IDENTIFICATION DATA:\n"
        f"- Common Name: {plant_data.get('plant_name')}\n"
        f"- Hindi Name: {plant_data.get('name_hindi')}\n"
        f"- Telugu Name: {plant_data.get('name_telugu')}\n"
        f"- Scientific Name: {plant_data.get('scientific_name')}\n"
        f"- Edible: {plant_data.get('edible')}\n"
        f"- Identification Confidence: {plant_data.get('confidence')}\n"
        f"- Toxicity Warnings: {plant_data.get('toxicity_warnings')}\n"
        f"- Lookalikes: {plant_data.get('lookalikes')}\n\n"
        f"LOCATION SAFETY DATA:\n"
        f"- Park Name: {location_data.get('pesticide', {}).get('park_name')}\n"
        f"- Pesticide Sprayed: {location_data.get('pesticide', {}).get('sprayed')}\n"
        f"- Days Since Sprayed: {location_data.get('pesticide', {}).get('days_ago')}\n"
        f"- Pesticide Safe To Forage: {location_data.get('pesticide', {}).get('safe_to_forage')}\n"
        f"- Soil Lead Level: {location_data.get('soil', {}).get('lead_level')} ppm (Safe limit: <= 80 ppm)\n"
        f"- Soil Safe: {location_data.get('soil', {}).get('safe')}\n"
        f"- Weather Conditions: {location_data.get('weather', {}).get('condition')}, "
        f"{location_data.get('weather', {}).get('temperature')}F\n\n"
        f"SAFE ALTERNATIVES NEARBY:\n"
        f"{json.dumps(safe_alternatives, indent=2)}\n"
    )

    # 1. Real ADK Execution Mode
    if HAS_ADK and api_key:
        try:
            logger.info("Running Safety Agent in Real ADK Mode")
            safety_agent = Agent(
                name="safety_agent",
                model="gemini-2.5-flash",
                instruction=SYSTEM_INSTRUCTION,
                tools=[], # Synthesizer, no tools needed
                description="Synthesizes botanical and environmental data to make a final food safety decision."
            )
            runner = InMemoryRunner(agent=safety_agent)
            
            import asyncio
            async def get_response():
                session = await runner.session_service.create_session(app_name="citybotanist", user_id="user")
                response_text = ""
                async for event in runner.run_async(
                    user_id=session.user_id,
                    session_id=session.id,
                    new_message=prompt
                ):
                    if hasattr(event, "content") and event.content:
                        response_text = event.content
                return response_text
                
            response_text = asyncio.run(get_response())
            
            # Determine decision based on response text
            decision = "DO NOT EAT"
            if "SAFE TO EAT" in response_text.upper() and "DO NOT EAT" not in response_text.upper().split("DECISION:")[1:]:
                decision = "SAFE TO EAT"
                
            return {
                "agent_response": response_text,
                "decision": decision
            }
        except Exception as e:
            logger.error(f"ADK Safety Agent failed: {e}. Falling back to rule-based execution.")

    # 2. Resilient Rule-Based Fallback Mode
    logger.info("Running Safety Agent in Mock LLM Fallback Mode")
    
    # Deterministic rule evaluations
    is_edible = plant_data.get("edible", False)
    is_sprayed = location_data.get("pesticide", {}).get("sprayed", False)
    is_soil_unsafe = not location_data.get("soil", {}).get("safe", True)
    is_low_confidence = plant_data.get("confidence", 0.0) < 0.80
    
    reasons = []
    if not is_edible:
        reasons.append(f"The plant '{plant_data.get('plant_name')}' (Hindi: {plant_data.get('name_hindi')}, Telugu: {plant_data.get('name_telugu')}) is naturally toxic or inedible ({plant_data.get('toxicity_warnings')}).")
    if is_sprayed:
        pesticide_info = location_data.get('pesticide', {})
        reasons.append(f"The location ({pesticide_info.get('park_name')}) was sprayed with {pesticide_info.get('chemical')} {pesticide_info.get('days_ago')} days ago (unsafe window is 14 days).")
    if is_soil_unsafe:
        soil_info = location_data.get('soil', {})
        reasons.append(f"The soil at this location has dangerous heavy metal levels (Lead: {soil_info.get('lead_level')} ppm, exceeds the safety threshold of 80 ppm). Source: {soil_info.get('contamination_source')}.")
    if is_low_confidence:
        reasons.append(f"The plant identification confidence ({plant_data.get('confidence') * 100:.1f}%) is below the safety threshold of 80.0%.")
        
    if reasons:
        decision = "DO NOT EAT"
        verdict_str = "**DECISION: DO NOT EAT** ❌"
        reasoning_str = "\n".join([f"- {r}" for r in reasons])
        
        # Format safe alternatives
        alt_str = ""
        
        # Defensive conversion and parsing
        parsed_alternatives = []
        if isinstance(safe_alternatives, list):
            parsed_alternatives = safe_alternatives
        elif isinstance(safe_alternatives, dict):
            if "result" in safe_alternatives:
                val = safe_alternatives["result"]
                if isinstance(val, str):
                    import ast
                    try:
                        parsed_alternatives = ast.literal_eval(val)
                    except Exception:
                        pass
                elif isinstance(val, list):
                    parsed_alternatives = val
        
        # Ensure we have a list of dictionaries
        if isinstance(parsed_alternatives, list):
            parsed_alternatives = [x for x in parsed_alternatives if isinstance(x, dict)]
        else:
            parsed_alternatives = []
            
        if parsed_alternatives:
            alt_str = "\n\n### Recommended Safe Alternative Locations:\n"
            for idx, alt in enumerate(parsed_alternatives, 1):
                alt_str += (
                    f"{idx}. **{alt.get('park_name', 'Unknown Park')}** ({alt.get('distance_km', 0.0)} km away)\n"
                    f"   - Status: {alt.get('chemical_status', 'Unknown')} | {alt.get('soil_status', 'Unknown')}\n"
                    f"   - Foraging Info: {alt.get('has_plant', 'Unknown')}\n"
                )
        else:
            alt_str = "\n\nNo monitored safe alternative locations were found within the metropolitan area."
            
        agent_response = (
            f"{verdict_str}\n\n"
            f"**Reasoning for safety restriction:**\n"
            f"{reasoning_str}"
            f"{alt_str}"
        )
    else:
        decision = "SAFE TO EAT"
        verdict_str = "**DECISION: SAFE TO EAT**  "
        agent_response = (
            f"{verdict_str}\n\n"
            f"**Reasoning:**\n"
            f"- The identified plant '{plant_data.get('plant_name')}' (Hindi: {plant_data.get('name_hindi')}, Telugu: {plant_data.get('name_telugu')}) is verified edible.\n"
            f"- Identification confidence is high ({plant_data.get('confidence') * 100:.1f}%).\n"
            f"- Municipal pesticide records indicate no recent spraying at {location_data.get('pesticide', {}).get('park_name')} within the 14-day window.\n"
            f"- Soil testing reports indicate lead levels ({location_data.get('soil', {}).get('lead_level')} ppm) are well below the agricultural hazard threshold of 80 ppm.\n"
            f"- Weather conditions are favorable ({location_data.get('weather', {}).get('condition')}, {location_data.get('weather', {}).get('temperature')}°F)."
        )
        
    return {
        "agent_response": agent_response,
        "decision": decision
    }
