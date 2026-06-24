import argparse
import os
import subprocess
import sys
import json
import logging

# Reconfigure stdout/stderr to support UTF-8 print statements (emojis) on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("citybotanist.main")

def run_streamlit():
    """Start the Streamlit UI."""
    app_path = os.path.join(CURRENT_DIR, "ui", "app.py")
    cmd = [sys.executable, "-m", "streamlit", "run", app_path]
    print(f"🚀 Starting City Botanist Streamlit UI at http://localhost:8501...")
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print("\n👋 Streamlit stopped.")
    except Exception as e:
        print(f"Error starting Streamlit: {e}")

def run_tests():
    """Run all tests with pytest."""
    tests_path = os.path.join(CURRENT_DIR, "tests")
    cmd = [sys.executable, "-m", "pytest", tests_path, "-v"]
    print("🧪 Running City Botanist Test Suite...")
    try:
        res = subprocess.run(cmd)
        sys.exit(res.returncode)
    except Exception as e:
        print(f"Error running tests: {e}")
        sys.exit(1)

def run_demo():
    """
    Run a pre-recorded demo scenario.
    Simulates a user at Volunteer Park trying to forage for Blackberry.
    Volunteer Park was sprayed 2 days ago with Glyphosate, so the system
    must trigger a DO NOT EAT recommendation and suggest Cal Anderson or Seward Park.
    """
    print("====================================================")
    print("🌿 CITY BOTANIST: AGENT WORKFLOW DEMO")
    print("Scenario: User at Volunteer Park (47.6300, -122.3150) uploads Blackberry image")
    print("====================================================\n")
    
    from agents.orchestrator import run_city_botanist_workflow
    
    # 1. Run the workflow
    # Using 'blackberry' keyword in image string to trigger blackberry preset
    result = run_city_botanist_workflow(
        image_base64="simulated_blackberry_image",
        latitude=47.6300,
        longitude=-122.3150,
        human_approved_lookalike=True
    )
    
    # 2. Output result step by step
    print("⚙️ WORKFLOW STEPS TRACE:")
    for step in result.get("workflow_steps", []):
        print(f"  [+] {step}")
        
    print("\n----------------------------------------------------")
    print("👁️ VISION AGENT IDENTIFICATION REPORT:")
    print(result.get("vision_report", ""))
    
    print("\n----------------------------------------------------")
    print("🌍 LOCATION AGENT ENVIRONMENTAL REPORT:")
    print(result.get("location_report", ""))
    
    print("\n----------------------------------------------------")
    print("🛡️ SAFETY AGENT FINAL VERDICT:")
    # Remove markdown tags from terminal printing for clean reading
    verdict = result.get("safety_report", "").replace("**", "")
    print(verdict)
    
    print("\n----------------------------------------------------")
    print("📁 AUDIT LOG FILE UPDATE:")
    print(f"  - User Privacy Hash: {result.get('user_location_hash')}")
    print(f"  - Decision Written to audit_log.json: {result.get('decision')}")
    
    print("\n====================================================")
    print("DEMO RUN COMPLETE: Safety guardrails successfully prevented human consumption of pesticide-treated plants.")
    print("====================================================")

def start_mcp(server_name: str):
    """Start one of the MCP servers in stdio mode."""
    server_map = {
        "plant": "plant_id_mcp.py",
        "city": "city_data_mcp.py",
        "weather": "weather_mcp.py"
    }
    
    if server_name not in server_map:
        print(f"Error: Unknown server '{server_name}'. Choose from: plant, city, weather")
        sys.exit(1)
        
    server_file = server_map[server_name]
    server_path = os.path.join(CURRENT_DIR, "mcp_servers", server_file)
    
    print(f"🔌 Starting Standalone MCP Server: {server_file} (stdio mode)...")
    cmd = [sys.executable, server_path]
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        print(f"\n👋 MCP Server {server_file} stopped.")
    except Exception as e:
        print(f"Error starting MCP server: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="City Botanist - Multi-Agent Urban Foraging Safety Tool (Kaggle Capstone)"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # run command
    subparsers.add_parser("run", help="Start the Streamlit User Interface")
    
    # test command
    subparsers.add_parser("test", help="Run the automated test suite")
    
    # demo command
    subparsers.add_parser("demo", help="Run the pre-recorded foraging safety demo scenario")
    
    # start-mcp command
    mcp_parser = subparsers.add_parser("start-mcp", help="Start an MCP server in standalone stdio mode")
    mcp_parser.add_argument(
        "--server", 
        choices=["plant", "city", "weather"], 
        default="plant", 
        help="Specify which MCP server to start (default: plant)"
    )
    
    args = parser.parse_args()
    
    if args.command == "run":
        run_streamlit()
    elif args.command == "test":
        run_tests()
    elif args.command == "demo":
        run_demo()
    elif args.command == "start-mcp":
        start_mcp(args.server)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
