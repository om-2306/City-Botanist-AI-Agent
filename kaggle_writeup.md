# Kaggle Capstone Submission: City Botanist 🌿
## Freestyle Track — Urban Foraging Safety Agent

### 1. Project Summary & Core Value Proposition
Urban foraging supports food sovereignty and reconnects city dwellers with nature. However, it carries two severe, high-stakes hazards:
1. **Botanical Misidentification:** Mistaking a toxic species (e.g., Poison Hemlock) for an edible one (e.g., Wild Carrot) is life-threatening.
2. **Environmental Toxicity:** Growing in soil contaminated with heavy metals (lead, arsenic) or parks sprayed with chemical herbicides (like glyphosate) makes even edible plants toxic.

**City Botanist** is a production-ready, multi-agent AI assistant built on the **Google Agent Development Kit (ADK)**. It combines advanced computer vision with local environmental database tools via the **Model Context Protocol (MCP)** to verify if a plant is safe to eat in a specific city location, all while preserving user location privacy.

---

### 2. Multi-Agent Design (Google ADK)
We designed a cooperative, sequential multi-agent network using the Google ADK. Each agent is modeled with distinct system instructions, safety guardrails, and specialized tool interfaces:

| Agent Name | Role | Core Prompts & Instructions | Tools Used |
| :--- | :--- | :--- | :--- |
| **Vision Agent** | Botanical Classifier | Identify plant species (Common English, Hindi, Telugu, and Scientific name), edibility status, and flag morphological lookalikes. | `identify_plant` (Plant ID MCP) |
| **Location Agent** | Environmental Analyst | Scan city logs for pesticide schedules, assess soil lead contamination, and read real-time weather forecasts. | `check_pesticide_spraying`, `get_soil_contamination`, `get_weather_forecast` (City Data & Weather MCPs) |
| **Safety Agent** | Final Risk Synthesizer | Perform sequential risk analysis (confidence, edibility, soil toxicity, spraying logs) and output a definitive **SAFE TO EAT** or **DO NOT EAT** decision. Recommends safe alternative parks if unsafe. | None (Cognitive Synthesis Agent) |

#### Orchestration Workflow
Managed by [orchestrator.py](file:///c:/Users/ompra/OneDrive/Documents/Kaggle%20Project%20for%20Hackathon/citybotanist/agents/orchestrator.py), the execution follows a strict sequence:
1. **Input Validation:** Verifies image size/format (<5MB, valid extensions) and GPS ranges.
2. **Privacy Scrubbing:** Location is anonymized immediately before processing.
3. **Identification Phase:** The Vision Agent is invoked. If plant confidence is `< 80%`, the orchestrator immediately triggers a `DO NOT EAT` decision.
4. **Human-in-the-Loop Lookalike Checkpoint:** If the plant has dangerous lookalikes (e.g. Blackberry vs. Nightshade), the orchestrator pauses execution and requires the user to explicitly verify morphological features (leaves, stalks, scent).
5. **Environmental Assessment:** The Location Agent pulls city spraying logs, heavy metal levels, and weather data.
6. **Safety Synthesis:** The Safety Agent evaluates all reports and issues the final verdict.
7. **Content Sanitization:** Any absolute safety assertions (e.g., "100% safe") are replaced with qualified statements, and a standard medical disclaimer is appended.
8. **Immutable Log:** Hashed coordinate records and decisions are appended to `audit_log.json`.

---

### 3. Tool Architecture (Model Context Protocol)
To ensure modularity and separation of concerns, we decoupled the agent logic from external services using the Model Context Protocol (MCP) powered by Python `fastmcp`:

1. **`plant_id_mcp.py` (Plant Identification Server):**
   - Integrates Gemini 2.5 Vision API to classify plant photos.
   - Falls back to a mock database indexing local flora (Blackberry, Dandelion, Poison Hemlock, etc.) for local development/testing without API keys.
2. **`city_data_mcp.py` (City Database Server):**
   - Connects to municipal spraying schedules and soil contamination archives.
   - Evaluates if soil lead concentrations are below the EPA/municipal threshold (80 ppm) and flags parks sprayed with pesticides (e.g., Glyphosate) within the last 14 days.
   - Contains a geospatial search tool to retrieve the 3 nearest safe parks of the same species if the current park is contaminated.
3. **`weather_mcp.py` (Weather Service Server):**
   - Queries the open-source **Open-Meteo API** to check temperature, precipitation, and wind speeds, ensuring foragers don't forage in heavy rain or unsafe storm conditions.

---

### 4. Security & Privacy Guardrails
Safety in urban foraging requires rigorous security boundaries. We implemented four distinct guardrails:

* **Location Anonymization:** Rounds user GPS coordinates to 2 decimal places. This limits accuracy to a ~1.1km grid, protecting precise user location data from external API logs while maintaining geospatial query accuracy for municipal data.
* **Confidence Gate:** Enforces a strict `confidence >= 80%` threshold on classification. Anything lower automatically prompts a `DO NOT EAT` verdict.
* **Content Safety Filter:** Utilizes regular expression matching to scan the synthesized safety reports. Absolute claims like *"completely safe"* or *"cures all illnesses"* are auto-rewritten to qualified statements like *"generally considered safe to consume"* or *"is traditionally believed to support wellness"*.
* **SHA-256 Hashed Audit Logging:** Generates a secure, non-reversible SHA-256 hash of the precise coordinates and logs it to `audit_log.json` alongside the final safety decision, creating a secure audit trail for agricultural officials.

---

### 5. Deployment & Production Readiness
* **Containerization:** The app is fully Dockerized using a lightweight Multi-stage build ([Dockerfile](file:///c:/Users/ompra/OneDrive/Documents/Kaggle%20Project%20for%20Hackathon/citybotanist/Dockerfile)).
* **Resilience:** If no `GEMINI_API_KEY` is present, the app degrades gracefully to a "Mock LLM Mode" to allow full offline demonstration and testing.
* **Automated Tests:** Comprehensive unit and integration test coverage ([tests/](file:///c:/Users/ompra/OneDrive/Documents/Kaggle%20Project%20for%20Hackathon/citybotanist/tests)) is run automatically with `pytest`, covering E2E foraging journeys, GPS validations, and audit logs.
* **One-Click Deploy:** [deploy.sh](file:///c:/Users/ompra/OneDrive/Documents/Kaggle%20Project%20for%20Hackathon/citybotanist/deploy.sh) automates container tag/push to Google Container Registry and deployment to Google Cloud Run.
