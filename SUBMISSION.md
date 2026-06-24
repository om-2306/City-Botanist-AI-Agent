# Kaggle Submission Guide: City Botanist 🏆

This document serves as the roadmap for submitting **City Botanist** to the **Kaggle AI Agents: Intensive Vibe Coding Capstone** (Freestyle Track).

---

## 📅 Submission Checklist

- [ ] **Code Repository:** Ensure all files in `/citybotanist/` are pushed and clean.
- [ ] **Tests Passing:** Verify that `python main.py test` executes successfully.
- [ ] **Video Pitch:** Record a 3-5 minute video demonstrating the agent.
- [ ] **Writeup:** Draft the technical writeup detailing agent prompts, MCP structure, and safety guardrails.
- [ ] **Kaggle Notebook / Spaces Link:** Ensure the web UI is deployed or can be executed out-of-the-box.

---

## 🎬 Video Pitch Script Outline (3-5 Minutes)

### 1. Hook & Problem Statement (0:00 - 0:45)
- **Visual:** Show a person looking at berries in a city park.
- **Audio:** "Urban foraging is an incredible way to connect with nature, but it carries hidden dangers. Is that wild garlic, or is it toxic Lily of the Valley? Was this park sprayed with weedkillers yesterday? Is the soil contaminated with industrial lead?"
- **Introduction:** "Meet City Botanist, an intelligent agent system that solves this by combining botanical vision with municipal safety logs and location privacy."

### 2. Live Demo: The Safe Path (0:45 - 1:45)
- **Visual:** Screen share of the Streamlit UI. Select Discovery Park. Upload a Dandelion image (use the simulation preset).
- **Action:** Click "Analyze Safety". Show the status spinner showing Vision Agent, Location Agent, and Safety Agent running.
- **Result:** Large green **SAFE TO EAT** banner appears. Point out the high confidence, clean pesticide logs, and clean soil levels.
- **Follow-up Chat:** Ask: "How do I cook dandelion?" Show the agent answering.

### 3. Live Demo: The Safety Guardrails (1:45 - 3:00)
- **Visual:** Switch location to Volunteer Park. Select Blackberry or Wild Garlic.
- **Action:** Click "Analyze Safety". Show the **Lookalike Checkpoint** halting execution. Confirm verification.
- **Result:** Large red **DO NOT EAT** banner. Highlight the pesticide chemical (Glyphosate, sprayed 2 days ago).
- **Key Feature:** Scroll to the **Safe Alternatives** panel. "Because Volunteer Park is sprayed, our agents searched the municipal databases and recommended these 3 safe, clean parks nearby instead."
- **Privacy:** Show the hashed location ID under the privacy dashboard. "We anonymized the GPS coordinates before doing any API checks to protect user privacy."

### 4. Technical Architecture & Closing (3:00 - 3:45)
- **Visual:** Show the text-based architecture diagram from the README.
- **Explanation:** Explain the Google ADK Agent structure, the standalone MCP servers built with FastMCP, and the fallback Mock LLM Runner.
- **Outro:** "City Botanist is production-ready, Dockerized, and fully tested. It represents a new standard for safe, context-aware AI agent applications. Thank you."

---

## 📝 Kaggle Writeup Structure

### 1. Summary
- Brief description of City Botanist and why it was built.

### 2. Multi-Agent Design (Google ADK)
- **Vision Agent:** Role and system prompts.
- **Location Agent:** Role and tool usage.
- **Safety Agent:** Reasoning synthesis.
- **Orchestrator:** How sequential workflows and human-in-the-loop checkpoints are managed.

### 3. Tool Architecture (Model Context Protocol)
- Details on the three MCP servers (`plant_id_mcp`, `city_data_mcp`, `weather_mcp`) and why FastMCP was selected.
- Open-Meteo API integration.

### 4. Security & Privacy Guardrails
- **Location Privacy:** 2-decimal rounding.
- **Misidentification protection:** 80% confidence gate.
- **Content Filter:** Scan for absolute safety assertions and append educational/medical disclaimers.
- **Audit Logging:** Hashing user GPS coordinates using SHA-256.

### 5. Deployment & Production Readiness
- Docker multi-stage configurations.
- Resilient API key fallbacks (Mock LLM mode).
- Testing coverage metrics.
