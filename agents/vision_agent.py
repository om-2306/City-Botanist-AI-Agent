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

logger = logging.getLogger("citybotanist.vision_agent")

SYSTEM_INSTRUCTION = (
    "You are a botanical expert specializing in urban plant identification. "
    "Analyze the uploaded image and identify the plant species using the identify_plant tool. "
    "Provide the common name (English), scientific name, Hindi name, Telugu name, and general edibility status. "
    "Always note potential lookalikes that could be dangerous. "
    "If confidence is below 80% (0.80), recommend against consumption. "
    "Structure your response clearly with headers: Common Name (English), Hindi Name, Telugu Name, Scientific Name, "
    "Edibility Status, Confidence, Lookalikes, and Warnings."
)

def identify_plant_tool(image_base64: str) -> str:
    """
    Identify a plant from an uploaded image (base64 string).
    Returns a JSON-formatted string with plant name, scientific name, edibility status, confidence, lookalikes, warnings, and description.
    """
    from agents.orchestrator import call_mcp_tool_sync
    try:
        result = call_mcp_tool_sync("plant_id_mcp.py", "identify_plant", {"image_base64": image_base64})
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error in identify_plant_tool: {e}")
        return json.dumps({"error": str(e), "plant_name": "Unknown", "confidence": 0.0})

def run_vision_agent(image_base64: str) -> Dict[str, Any]:
    """
    Run the Vision Agent on the base64 image.
    Uses Google ADK if API keys are available, otherwise runs a high-fidelity mock fallback.
    """
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    
    # 1. Real ADK Execution Mode
    if HAS_ADK and api_key:
        try:
            logger.info("Running Vision Agent in Real ADK Mode")
            vision_agent = Agent(
                name="vision_agent",
                model="gemini-2.5-flash",
                instruction=SYSTEM_INSTRUCTION,
                tools=[identify_plant_tool],
                description="Identifies plants from base64 images and extracts scientific metadata."
            )
            runner = InMemoryRunner(agent=vision_agent)
            
            prompt = f"Please identify the plant in this base64 image: {image_base64[:500]}..."
            # For ADK 2.0+, run the runner in a session
            # We can use runner.run if synchronous, or write a helper to manage the session
            # The runner's run method might require session parameters; let's handle it
            import asyncio
            
            # Simple wrapper to run async run_async of ADK runner synchronously
            async def get_response():
                session = await runner.session_service.create_session(app_name="citybotanist", user_id="user")
                response_text = ""
                async for event in runner.run_async(
                    user_id=session.user_id,
                    session_id=session.id,
                    new_message=prompt
                ):
                    # Gather text from event content
                    if hasattr(event, "content") and event.content:
                        response_text = event.content
                return response_text
                
            response_text = asyncio.run(get_response())
            
            # If the response is gathered, parse the tool output to return a structured dictionary
            # Since the LLM text output is conversational, we also extract the raw tool call result
            # to keep data structured and highly precise for downstream agents
            tool_data = call_mcp_tool_sync("plant_id_mcp.py", "identify_plant", {"image_base64": image_base64})
            return {
                "agent_response": response_text,
                "structured_data": tool_data
            }
        except Exception as e:
            logger.error(f"ADK Vision Agent failed: {e}. Falling back to rule-based execution.")
            
    # 2. Resilient Rule-Based Fallback Mode
    logger.info("Running Vision Agent in Mock LLM Fallback Mode")
    # Directly call the MCP tool to simulate tool call and format the response
    tool_data = call_mcp_tool_sync("plant_id_mcp.py", "identify_plant", {"image_base64": image_base64})
    
    plant_name = tool_data.get("plant_name", "Unknown")
    name_hindi = tool_data.get("name_hindi", "Unknown")
    name_telugu = tool_data.get("name_telugu", "Unknown")
    sci_name = tool_data.get("scientific_name", "Unknown")
    edible = "Yes" if tool_data.get("edible", False) else "No"
    conf = tool_data.get("confidence", 0.0)
    lookalikes = ", ".join(tool_data.get("lookalikes", []))
    warnings = tool_data.get("toxicity_warnings", "None")
    description = tool_data.get("description", "")
    
    agent_response = (
        f"### Botanical Analysis Report\n\n"
        f"**Common Name (English)**: {plant_name}\n"
        f"**Hindi Name**: {name_hindi}\n"
        f"**Telugu Name**: {name_telugu}\n"
        f"**Scientific Name**: {sci_name}\n"
        f"**Edibility Status**: {'Edible' if edible == 'Yes' else 'Toxic/Inedible'}\n"
        f"**Confidence**: {conf * 100:.1f}%\n"
        f"**Lookalikes**: {lookalikes if lookalikes else 'None registered'}\n"
        f"**Warnings**: {warnings}\n\n"
        f"**Description**: {description}"
    )
    
    return {
        "agent_response": agent_response,
        "structured_data": tool_data
    }
