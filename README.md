# City Botanist 🌿

City Botanist helps urban foragers identify plants from images AND determine if they are safe to eat by cross-referencing municipal pesticide spraying schedules, soil contamination archives, and real-time weather forecasts.

---

## 📖 Table of Contents
1. [Overview & Problem Statement](#-overview--problem-statement)
2. [Architecture Diagram](#%EF%B8%8F-architecture-diagram)
3. [Features](#-features)
4. [Technical Stack](#-technical-stack)
5. [Installation & Setup](#-installation--setup)
6. [Usage Guide](#-usage-guide)
7. [Running Tests](#-running-tests)
8. [Docker Deployment](#-docker-deployment)
9. [Google Cloud Run Deployment](#-google-cloud-run-deployment)
10. [Security & Location Privacy](#-security--location-privacy)

---

## 🔍 Overview & Problem Statement

Urban foraging is a growing practice that supports food sovereignty, local ecosystems, and green connection. However, foraging in cities carries two distinct, high-risk hazards:
1. **Misidentification:** Mistaking a toxic plant (e.g., Poison Hemlock, Lily of the Valley) for an edible one (e.g., Wild Carrot, Wild Garlic) can lead to severe poisoning or death.
2. **Environmental Toxicity:** An edible plant growing in a park sprayed with pesticides (e.g., Glyphosate) or in soil contaminated with heavy metals (e.g., Lead, Arsenic) is unsafe for consumption.

**City Botanist** solves this by establishing a multi-agent network that automates botanical identification, scans municipal health databases, assesses weather, applies security guardrails, and provides a conversational interface for foragers—all while preserving location privacy.

---

## 🖥️ Architecture Diagram

```
                 [ USER / STREAMLIT UI ]
                            │
                            ▼
                  [ INPUT VALIDATION ]
            (Image Size/Format, GPS Ranges)
                            │
                            ▼
                [ LOCATION ANONYMIZATION ]
             (Coords rounded to 2 decimals)
                            │
                            ▼
                  [ AGENT ORCHESTRATOR ]
                            │
      ┌─────────────────────┼─────────────────────┐
      ▼                     ▼                     ▼
[ VISION AGENT ]    [ LOCATION AGENT ]    [ SAFETY AGENT ]
      │                     │                     │
      ▼                     ▼                     ▼
[ PLANT ID MCP ]    [ CITY DATA MCP ]             │ (Synthesizes results)
 (Mock database      (Pesticide schedules,         │
  + Gemini vision)    Soil lead levels,           │
                            Alternatives)         │
                            │                     │
                            ▼                     │
                      [ WEATHER MCP ]             │
                       (Open-Meteo API)           │
                            │                     │
                            └─────────────────────┼──────────────────┐
                                                  ▼                  ▼
                                        [ CONTENT FILTERING ]  [ AUDIT LOG ]
                                          (Disclaimers &         (SHA-256 Hashed
                                         claim validation)        coordinates)
```

---

## ✨ Features

- **Multi-Agent Coordination (Google ADK):** Orchestrates three specialized agents (Vision, Location, Safety) using sequential reasoning.
- **Model Context Protocol (MCP):** Interfaces with separate, decoupled tools (Plant identification, City databases, and Weather services) hosted on stdio MCP servers.
- **Location Privacy:** Anonymizes GPS coordinates (rounds to 2 decimal places, ~1.1km precision) before calling any external APIs.
- **Plant Misidentification Guardrail:** Enforces a hard `DO NOT EAT` verdict if identification confidence falls below 80%.
- **Lookalike Checkpoint (Human-in-the-Loop):** Halts safety recommendation if the identified plant has highly toxic lookalikes, requiring explicit user verification of morphological features (scent, leaves).
- **Soil & Pesticide Audit:** Flags locations sprayed within 14 days or containing lead levels above 80 ppm.
- **Safe Alternatives Recommendation:** Recommends the 3 closest safe city parks offering the same plant if the user's current location is toxic.
- **Follow-up Chat:** Allows foragers to chat with the agent regarding cooking preparations or historical facts.
- **Audit Trails:** Logs hashed user locations and agent decisions to `audit_log.json`.

---

## 🛠️ Technical Stack

- **Framework:** Google Agent Development Kit (ADK)
- **UI:** Streamlit (Nature-themed theme)
- **Protocol:** Model Context Protocol (MCP) using Python `fastmcp`
- **APIs:** Gemini (via Google AI Studio), Open-Meteo (Free weather forecasts)
- **Validation:** Pydantic v2
- **Testing:** Pytest, Pytest-Asyncio
- **Deployment:** Docker, Bash scripts for Google Cloud Run / Kaggle Spaces

---

## ⚙️ Installation & Setup

### Prerequisites
- Python 3.11 or newer
- Docker (optional, for containerization)

### Setup Instructions
1. Clone the repository and navigate to the project directory:
   ```bash
   cd citybotanist
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```

3. Install all dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   Create a `.env` file based on `.env.example`:
   ```bash
   cp .env.example .env
   # Edit .env and enter your GEMINI_API_KEY
   ```
   *Note: If no API key is provided, the application runs in a local "Mock LLM Mode" to support testing without credentials.*

---

## 🚀 Usage Guide

Use `main.py` to control all parts of the application:

### 1. Start the Streamlit User Interface
```bash
python main.py run
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

### 2. Run the Interactive Safety Demo
Simulate a foraging scenario at Volunteer Park (recently sprayed with Glyphosate) to see how the agents coordinate to protect the user:
```bash
python main.py demo
```

### 3. Run Standalone MCP Servers
Test or inspect the MCP servers in stdio mode:
```bash
python main.py start-mcp --server plant
python main.py start-mcp --server city
python main.py start-mcp --server weather
```

---

## 🧪 Running Tests

Run the complete suite of unit and integration tests:
```bash
python main.py test
```

Tests cover:
- **Agents (`tests/test_agents.py`):** Agent prompts and reasoning loops.
- **MCP (`tests/test_mcp.py`):** Tool calls, mock data indexing, and weather lookups.
- **Security (`tests/test_security.py`):** Anonymization, claim filters, and validation.
- **E2E (`tests/test_e2e.py`):** Integration journey of a user uploading images near a sprayed location.

---

## 🐳 Docker Deployment

Build and run the application locally inside a secure container:
```bash
# Build
docker build -t citybotanist .

# Run (make sure to pass your .env file)
docker run -p 8501:8501 --env-file .env citybotanist
```

---

## ☁️ Google Cloud Run Deployment

Deploy the application to Google Cloud Run with one command:
```bash
# Set execute permissions
chmod +x deploy.sh

# Edit deploy.sh with your GCP project ID and run
./deploy.sh
```

---

## 🔒 Security & Location Privacy

City Botanist prioritizes user safety and privacy:
- **GPS Privacy:** Precise coordinate readings (e.g., `47.630012, -122.315089`) are immediately rounded to two decimal places (`47.63, -122.32`) inside `security/guardrails.py` before any network or external database calls.
- **Anonymized Logs:** The audit logger records only the SHA-256 hash of the coordinates to verify records without exposing the user's home or real location.
- **Content Claim Guardrail:** Every recommendation is scanned to remove absolute safety assertions (e.g., "100% safe") and append botanical, educational, and medical disclaimers.
