import os
import sys
import json
import logging
import asyncio
import importlib.util
import base64

from typing import Dict, Any, List, Tuple, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("citybotanist.orchestrator")

# Dynamic fallback importer for MCP tools
def call_mcp_tool_directly(server_filename: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Import the MCP server file dynamically and call the tool function in-process."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    server_path = os.path.join(project_root, "mcp_servers", server_filename)
    module_name = server_filename.replace(".py", "")
    
    try:
        if module_name in sys.modules:
            module = sys.modules[module_name]
        else:
            spec = importlib.util.spec_from_file_location(module_name, server_path)
            if spec is None or spec.loader is None:
                raise ImportError(f"Could not load spec for {server_path}")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
        if hasattr(module, tool_name):
            func = getattr(module, tool_name)
            if asyncio.iscoroutinefunction(func):
                # Call async function synchronously
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(func(**arguments))
                finally:
                    loop.close()
            else:
                return func(**arguments)
        else:
            # Fallback check if it's registered on FastMCP
            if hasattr(module, "mcp") and hasattr(module.mcp, "_tools"):
                # Access FastMCP internal tools mapping if possible
                for t in module.mcp._tools:
                    if t.name == tool_name:
                        if asyncio.iscoroutinefunction(t.fn):
                            loop = asyncio.new_event_loop()
                            try:
                                return loop.run_until_complete(t.fn(**arguments))
                            finally:
                                loop.close()
                        else:
                            return t.fn(**arguments)
            return {"error": f"Tool '{tool_name}' not found on server directly"}
    except Exception as e:
        logger.error(f"Failed to invoke tool '{tool_name}' directly: {e}")
        return {"error": f"Failed to invoke tool directly: {str(e)}"}

async def call_mcp_tool(server_filename: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Run an MCP server as a subprocess and call a tool using standard StdioClient."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    server_path = os.path.join(project_root, "mcp_servers", server_filename)
    
    # Check if file exists
    if not os.path.exists(server_path):
        logger.warning(f"Server script {server_path} not found. Trying direct fallback.")
        return call_mcp_tool_directly(server_filename, tool_name, arguments)
        
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[server_path]
    )
    
    try:
        # Wrap stdio subprocess client with timeout
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)
                if result.content and len(result.content) > 0:
                    if len(result.content) > 1:
                        parsed_list = []
                        for block in result.content:
                            text_content = block.text
                            try:
                                parsed_list.append(json.loads(text_content))
                            except json.JSONDecodeError:
                                import ast
                                try:
                                    parsed_list.append(ast.literal_eval(text_content))
                                except Exception:
                                    parsed_list.append(text_content)
                        return parsed_list
                    else:
                        text_content = result.content[0].text
                        try:
                            return json.loads(text_content)
                        except json.JSONDecodeError:
                            import ast
                            try:
                                return ast.literal_eval(text_content)
                            except Exception:
                                return {"result": text_content}
                return {"error": "Empty response from tool"}
    except Exception as e:
        logger.warning(f"MCP subprocess call failed for {server_filename}/{tool_name}: {e}. Trying direct fallback.")
        return call_mcp_tool_directly(server_filename, tool_name, arguments)

def call_mcp_tool_sync(server_filename: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Synchronous wrapper for calling MCP tools (convenient for streamlit/runners)."""
    try:
        # Run in existing or new event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            # If loop is already running (e.g. inside another async context), call direct fallback
            return call_mcp_tool_directly(server_filename, tool_name, arguments)
        else:
            return loop.run_until_complete(call_mcp_tool(server_filename, tool_name, arguments))
    except Exception as e:
        logger.error(f"Sync call to MCP tool failed: {e}")
        return call_mcp_tool_directly(server_filename, tool_name, arguments)

# Multi-agent orchestrator function
def run_city_botanist_workflow(
    image_base64: str,
    latitude: float,
    longitude: float,
    human_approved_lookalike: bool = False
) -> Dict[str, Any]:
    """
    Coordinative workflow:
    1. Input validation (Image size/format, GPS bounds)
    2. Location anonymization (rounds coordinates to 2 decimals)
    3. Vision Agent: Identifies plant species from image
    4. Guardrail: If confidence < 80%, abort or recommend DO NOT EAT
    5. Check Lookalike Warning: If dangerous lookalike is listed, flag for UI Human-in-the-Loop Checkpoint
    6. Location Agent: Evaluates environmental spraying, heavy metal soil contamination, and weather
    7. Safety Agent: Synthesizes reports to make a definitive safety recommendation (SAFE/DO NOT EAT)
    8. Guardrail: Sanitizes safety claims and appends medical disclaimers
    9. Log to audit_log.json
    """
    from security import guardrails
    from agents.vision_agent import run_vision_agent
    from agents.location_agent import run_location_agent
    from agents.safety_agent import run_safety_agent
    
    workflow_steps = []
    tool_calls_log = []
    
    # Step 1: Validate GPS
    workflow_steps.append("Validating GPS coordinates...")
    if not guardrails.validate_gps(latitude, longitude):
        return {
            "success": False,
            "error": "Invalid GPS coordinates. Latitude must be between -90 and 90, Longitude between -180 and 180.",
            "workflow_steps": workflow_steps
        }
        
    # Step 2: Validate Image
    workflow_steps.append("Validating uploaded image...")
    # Extract pure base64 content by stripping prefix and metadata suffixes
    clean_b64 = image_base64
    if "base64," in clean_b64:
        clean_b64 = clean_b64.split("base64,", 1)[1]
    elif "," in clean_b64:
        clean_b64 = clean_b64.split(",", 1)[1]
    clean_b64 = clean_b64.split(";")[0].strip()
    
    if len(image_base64) <= 100:
        # Short strings are allowed for CLI test/demo simulation
        workflow_steps.append("Short string input detected. Skipping physical image file validation for testing.")
    else:
        try:
            img_bytes = base64.b64decode(clean_b64)
            is_valid_img, img_err = guardrails.validate_image_file(img_bytes)
            if not is_valid_img:
                return {
                    "success": False,
                    "error": f"Image validation failed: {img_err}",
                    "workflow_steps": workflow_steps
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Invalid image encoding: {str(e)}",
                "workflow_steps": workflow_steps
            }

    # Step 3: Anonymize Location
    workflow_steps.append("Applying Location Privacy Protection (rounding coordinates to 2 decimals)...")
    anon_lat, anon_lon = guardrails.anonymize_location(latitude, longitude)
    logger.info(f"Anonymized user coordinates from ({latitude}, {longitude}) to ({anon_lat}, {anon_lon})")
    
    # Step 4: Run Vision Agent
    workflow_steps.append("Vision Agent: Analyzing image and querying Plant ID MCP Server...")
    vision_result = run_vision_agent(image_base64)
    plant_data = vision_result.get("structured_data", {})
    plant_name = plant_data.get("plant_name", "Unknown")
    confidence = plant_data.get("confidence", 0.0)
    lookalikes = plant_data.get("lookalikes", [])
    
    tool_calls_log.append({
        "server": "plant_id_mcp.py",
        "tool": "identify_plant",
        "arguments": {"image_base64": f"<{len(image_base64)} chars>"},
        "result": plant_data
    })
    
    # Step 5: Confidence threshold check
    workflow_steps.append("Applying Plant Misidentification Guardrail...")
    is_conf_ok = guardrails.validate_plant_id_confidence(confidence)
    
    # Step 6: Human-in-the-Loop Checkpoint (Dangerous Lookalikes)
    # If the identified plant has registered dangerous lookalikes and the user hasn't explicitly checked the approval box,
    # we flag a checkpoint warning requiring human acknowledgment
    checkpoint_required = False
    checkpoint_message = ""
    
    # Look for known toxic lookalikes in the database (e.g. Lily of the Valley for Wild Garlic, Hemlock for Queen Anne's Lace)
    dangerous_lookalikes = ["lily of the valley", "poison hemlock", "death cap", "deadly nightshade", "foxglove"]
    matched_danger_lookalikes = [l for l in lookalikes if l.lower() in dangerous_lookalikes]
    
    if matched_danger_lookalikes and not human_approved_lookalike:
        checkpoint_required = True
        checkpoint_message = (
            f"WARNING: The identified plant '{plant_name}' has dangerous, potentially lethal lookalikes: "
            f"{', '.join(matched_danger_lookalikes)}. Please confirm you have inspected the leaves "
            f"and scent to rule out these toxic species before proceeding."
        )
        workflow_steps.append(f"Lookalike Checkpoint triggered: {checkpoint_message}")
        
    # If the identification is extremely low confidence or plant is unknown, skip further analysis and return DO NOT EAT
    if not is_conf_ok or plant_name == "Unknown":
        workflow_steps.append("Enforcing immediate safety restriction: Confidence is below 80% or plant is unknown.")
        
        # Run safety agent with low confidence data
        fake_location_data = {"pesticide": {"sprayed": False, "safe_to_forage": True, "park_name": "Unregistered"}, "soil": {"safe": True, "lead_level": 0.0}, "weather": {"condition": "Unknown", "temperature": 65}}
        safety_result = run_safety_agent(plant_data, fake_location_data, [], anon_lat, anon_lon)
        
        # Apply content safety filters
        sanitized = guardrails.check_safety_claims(safety_result["agent_response"])
        final_text = sanitized["modified_text"]
        
        # Write log
        user_hash = guardrails.log_audit_transaction(
            latitude=latitude,
            longitude=longitude,
            plant_identified=plant_name,
            safety_decision="DO NOT EAT",
            reasoning=f"Plant misidentification guardrail triggered. Confidence: {confidence*100:.1f}%.",
            tool_calls=tool_calls_log
        )
        
        return {
            "success": True,
            "decision": "DO NOT EAT",
            "plant_name": plant_name,
            "name_hindi": plant_data.get("name_hindi", "Unknown"),
            "name_telugu": plant_data.get("name_telugu", "Unknown"),
            "scientific_name": plant_data.get("scientific_name", "Unknown"),
            "confidence": confidence,
            "vision_report": vision_result.get("agent_response"),
            "location_report": "Location checks skipped due to low plant identification confidence.",
            "safety_report": final_text,
            "warnings": ["Plant identification confidence is below 80.0%. Consumption is prohibited."],
            "workflow_steps": workflow_steps,
            "user_location_hash": user_hash,
            "checkpoint_required": False,
            "safe_alternatives": []
        }

    # Step 7: Run Location Agent
    workflow_steps.append("Location Agent: Checking pesticide spraying, soil contamination, and weather databases...")
    location_result = run_location_agent(anon_lat, anon_lon)
    location_data = location_result.get("structured_data", {})
    
    tool_calls_log.append({
        "server": "city_data_mcp.py",
        "tool": "check_pesticide_spraying",
        "arguments": {"latitude": anon_lat, "longitude": anon_lon},
        "result": location_data.get("pesticide")
    })
    tool_calls_log.append({
        "server": "city_data_mcp.py",
        "tool": "get_soil_contamination",
        "arguments": {"latitude": anon_lat, "longitude": anon_lon},
        "result": location_data.get("soil")
    })
    tool_calls_log.append({
        "server": "weather_mcp.py",
        "tool": "get_weather",
        "arguments": {"latitude": anon_lat, "longitude": anon_lon},
        "result": location_data.get("weather")
    })

    # Step 8: Get Safe Alternatives (if location is unsafe, or if requested)
    safe_alternatives = []
    is_sprayed = location_data.get("pesticide", {}).get("sprayed", False)
    is_soil_unsafe = not location_data.get("soil", {}).get("safe", True)
    is_plant_toxic = not plant_data.get("edible", False)
    
    if is_sprayed or is_soil_unsafe or is_plant_toxic or checkpoint_required:
        workflow_steps.append("Querying City Data MCP for safe foraging alternatives...")
        raw_alternatives = call_mcp_tool_sync(
            "city_data_mcp.py",
            "find_safe_alternatives",
            {"latitude": anon_lat, "longitude": anon_lon, "plant_name": plant_name}
        )
        
        # Defensive conversion and parsing
        parsed_alternatives = []
        if isinstance(raw_alternatives, list):
            parsed_alternatives = raw_alternatives
        elif isinstance(raw_alternatives, dict):
            if "park_name" in raw_alternatives:
                parsed_alternatives = [raw_alternatives]
            elif "result" in raw_alternatives:
                val = raw_alternatives["result"]
                if isinstance(val, str):
                    import ast
                    try:
                        parsed_alternatives = ast.literal_eval(val)
                    except Exception:
                        pass
                elif isinstance(val, list):
                    parsed_alternatives = val
        
        if isinstance(parsed_alternatives, list):
            safe_alternatives = [x for x in parsed_alternatives if isinstance(x, dict)]
        else:
            safe_alternatives = []
            
        tool_calls_log.append({
            "server": "city_data_mcp.py",
            "tool": "find_safe_alternatives",
            "arguments": {"latitude": anon_lat, "longitude": anon_lon, "plant_name": plant_name},
            "result": safe_alternatives
        })

    # If Lookalike Checkpoint is active and not yet approved, we halt before the Safety Agent runs
    # This prevents giving a "SAFE TO EAT" recommendation until the user confirms lookalike inspection
    if checkpoint_required:
        workflow_steps.append("Halting workflow: Awaiting human confirmation of dangerous lookalikes.")
        return {
            "success": True,
            "decision": "DO NOT EAT",
            "plant_name": plant_name,
            "name_hindi": plant_data.get("name_hindi", "Unknown"),
            "name_telugu": plant_data.get("name_telugu", "Unknown"),
            "scientific_name": plant_data.get("scientific_name"),
            "confidence": confidence,
            "vision_report": vision_result.get("agent_response"),
            "location_report": location_result.get("agent_response"),
            "safety_report": f"**DECISION: DO NOT EAT (AWAITING CONFIRMATION)**\n\n{checkpoint_message}",
            "checkpoint_required": True,
            "checkpoint_message": checkpoint_message,
            "workflow_steps": workflow_steps,
            "safe_alternatives": safe_alternatives
        }

    # Step 9: Run Safety Agent
    workflow_steps.append("Safety Agent: Synthesizing plant identification and environmental safety data...")
    safety_result = run_safety_agent(
        plant_data=plant_data,
        location_data=location_data,
        safe_alternatives=safe_alternatives,
        original_lat=anon_lat,
        original_lon=anon_lon
    )
    
    # Step 10: Apply Content Safety Filter
    workflow_steps.append("Applying Content Safety Filters (disclaimers and claims verification)...")
    sanitized = guardrails.check_safety_claims(safety_result["agent_response"])
    final_safety_report = sanitized["modified_text"]
    
    # Step 11: Write Audit Log
    workflow_steps.append("Logging transaction to audit_log.json...")
    user_hash = guardrails.log_audit_transaction(
        latitude=latitude,
        longitude=longitude,
        plant_identified=plant_name,
        safety_decision=safety_result["decision"],
        reasoning=final_safety_report,
        tool_calls=tool_calls_log
    )
    
    workflow_steps.append("Workflow completed successfully.")
    
    return {
        "success": True,
        "decision": safety_result["decision"],
        "plant_name": plant_name,
        "name_hindi": plant_data.get("name_hindi", "Unknown"),
        "name_telugu": plant_data.get("name_telugu", "Unknown"),
        "scientific_name": plant_data.get("scientific_name"),
        "confidence": confidence,
        "vision_report": vision_result.get("agent_response"),
        "location_report": location_result.get("agent_response"),
        "safety_report": final_safety_report,
        "checkpoint_required": False,
        "workflow_steps": workflow_steps,
        "user_location_hash": user_hash,
        "safe_alternatives": safe_alternatives
    }
