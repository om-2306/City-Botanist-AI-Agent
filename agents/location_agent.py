import os
import json
import logging
from typing import Dict, Any

try:
    from google.adk.agents.llm_agent import Agent
    from google.adk.runners import InMemoryRunner
    HAS_ADK = True
except ImportError:
    HAS_ADK = False

from agents.orchestrator import call_mcp_tool_sync

logger = logging.getLogger("citybotanist.location_agent")

SYSTEM_INSTRUCTION = (
    "You are an environmental safety analyst. Given GPS coordinates, check municipal databases "
    "for recent pesticide spraying, soil contamination reports, and current weather conditions using the provided tools. "
    "Provide a detailed safety assessment for foraging at this location. "
    "State clearly: the park name (if matched), whether pesticides were sprayed in the last 14 days, "
    "whether soil lead levels are safe (< 80 ppm), and the weather forecast. "
    "Identify any immediate environmental risks. Structure your response with clear bullet points."
)

def check_pesticide_spraying_tool(latitude: float, longitude: float) -> str:
    """Check pesticide spraying records at given coordinates."""
    from agents.orchestrator import call_mcp_tool_sync
    try:
        return json.dumps(call_mcp_tool_sync("city_data_mcp.py", "check_pesticide_spraying", {"latitude": latitude, "longitude": longitude}))
    except Exception as e:
        logger.error(f"Error in check_pesticide_spraying_tool: {e}")
        return json.dumps({"error": str(e), "sprayed": False, "safe_to_forage": True})

def get_soil_contamination_tool(latitude: float, longitude: float) -> str:
    """Check soil contamination levels (lead, etc.) at given coordinates."""
    from agents.orchestrator import call_mcp_tool_sync
    try:
        return json.dumps(call_mcp_tool_sync("city_data_mcp.py", "get_soil_contamination", {"latitude": latitude, "longitude": longitude}))
    except Exception as e:
        logger.error(f"Error in get_soil_contamination_tool: {e}")
        return json.dumps({"error": str(e), "safe": True, "lead_level": 0.0})

def get_weather_tool(latitude: float, longitude: float) -> str:
    """Retrieve weather conditions at given coordinates."""
    from agents.orchestrator import call_mcp_tool_sync
    try:
        return json.dumps(call_mcp_tool_sync("weather_mcp.py", "get_weather", {"latitude": latitude, "longitude": longitude}))
    except Exception as e:
        logger.error(f"Error in get_weather_tool: {e}")
        return json.dumps({"error": str(e), "condition": "Unknown", "temperature": 65.0})

def run_location_agent(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Run the Location Agent on given coordinates.
    Uses Google ADK if API keys are available, otherwise runs a high-fidelity mock fallback.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    
    # 1. Real ADK Execution Mode
    if HAS_ADK and api_key:
        try:
            logger.info("Running Location Agent in Real ADK Mode")
            location_agent = Agent(
                name="location_agent",
                model="gemini-2.5-flash",
                instruction=SYSTEM_INSTRUCTION,
                tools=[check_pesticide_spraying_tool, get_soil_contamination_tool, get_weather_tool],
                description="Checks environmental safety data (spraying, soil, weather) at GPS coordinates."
            )
            runner = InMemoryRunner(agent=location_agent)
            
            prompt = f"Please analyze safety and weather conditions at coordinates: latitude={latitude}, longitude={longitude}"
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
            
            # Fetch structured data directly for downstream consumption
            pesticide_data = call_mcp_tool_sync("city_data_mcp.py", "check_pesticide_spraying", {"latitude": latitude, "longitude": longitude})
            soil_data = call_mcp_tool_sync("city_data_mcp.py", "get_soil_contamination", {"latitude": latitude, "longitude": longitude})
            weather_data = call_mcp_tool_sync("weather_mcp.py", "get_weather", {"latitude": latitude, "longitude": longitude})
            
            return {
                "agent_response": response_text,
                "structured_data": {
                    "pesticide": pesticide_data,
                    "soil": soil_data,
                    "weather": weather_data
                }
            }
        except Exception as e:
            logger.error(f"ADK Location Agent failed: {e}. Falling back to rule-based execution.")
            
    # 2. Resilient Rule-Based Fallback Mode
    logger.info("Running Location Agent in Mock LLM Fallback Mode")
    pesticide_data = call_mcp_tool_sync("city_data_mcp.py", "check_pesticide_spraying", {"latitude": latitude, "longitude": longitude})
    soil_data = call_mcp_tool_sync("city_data_mcp.py", "get_soil_contamination", {"latitude": latitude, "longitude": longitude})
    weather_data = call_mcp_tool_sync("weather_mcp.py", "get_weather", {"latitude": latitude, "longitude": longitude})
    
    park_name = pesticide_data.get("park_name", "Unregistered Location")
    sprayed = "Yes" if pesticide_data.get("sprayed", False) else "No"
    chemical = pesticide_data.get("chemical", "None")
    days_ago = pesticide_data.get("days_ago", 999)
    lead = soil_data.get("lead_level", 0.0)
    soil_safe = "Safe" if soil_data.get("safe", True) else "Unsafe (High Lead)"
    source = soil_data.get("contamination_source", "None")
    
    temp = weather_data.get("temperature", 65.0)
    humidity = weather_data.get("humidity", 50.0)
    rain = weather_data.get("recent_rainfall", 0.0)
    cond = weather_data.get("condition", "Clear")
    
    agent_response = (
        f"### Location Safety Report: {park_name}\n\n"
        f"- **Pesticide Spraying Status**: {sprayed} (Chemical: {chemical}, sprayed {days_ago} days ago)\n"
        f"- **Soil Contamination Status**: {soil_safe} (Lead level: {lead} ppm, Source: {source})\n"
        f"- **Current Weather**: {cond}, {temp}°F, Humidity: {humidity}%, Recent Rain: {rain} inches\n"
        f"- **Location Foraging Viability**: {'Safe' if (pesticide_data.get('safe_to_forage', True) and soil_data.get('safe', True)) else 'UNSAFE'}\n"
    )
    
    return {
        "agent_response": agent_response,
        "structured_data": {
            "pesticide": pesticide_data,
            "soil": soil_data,
            "weather": weather_data
        }
    }
