# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AgentTwister is an AI-powered offensive security research tool for ethical red-teaming of LLM-powered applications. It uses a multi-agent pipeline to analyze, plan, and generate adversarial payloads for testing AI systems against the OWASP LLM Top 10 vulnerabilities.

## Commands

### Development
```bash
# Install dependencies
pip install -e ".[dev]"

# Run the development server with hot reload
cd backend
uvicorn app.main:app --reload

# Run a single test file
pytest backend/tests/verify_payloads.py -v

# Run all tests
pytest backend/tests/ -v

# Run tests with coverage
pytest --cov=backend/tests/
```

### Code Quality
```bash
# Lint with ruff
ruff check backend/

# Format with black
black backend/

# Type check with mypy
mypy backend/app/
```
## Architecture

### Backend Structure
```
backend/
├── app/
│   ├── main.py              # FastAPI app entry point, lifespan management
│   ├── core/               # Configuration, logging
│   ├── agents/
│   │   ├── base_agent.py   # Google ADK-inspired agent base class
│   │   ├── registry.py      # Agent registration and discovery
│   │   ├── tools/            # Tool definitions for agents
│   │   ├── a2a/              # Agent-to-Agent protocol adapter
│   │   └── resilience/      # Circuit breaker, exponential backoff
│   ├── models/
│   │   ├── payload.py       # Payload data models (Pydantic)
│   │   └── evidence_bundle.py
│   ├── api/
│   │   └── routes/
│   │       └── payloads.py  # REST API endpoints
│   └── services/
│       ├── firestore_client.py   # Firebase/Firestore integration
│       └── payload_library.py   # Payload template management
├── tests/
│   └── verify_payloads.py
└── scripts/
    └── seed_firestore.py
```

### Key Patterns

1. **Agent System**: Built on `BaseAgent` class in `backend/app/agents/base_agent.py`. All specialized agents (Analyst, Planner, Architect, Payload Engineer, Reviewer, Formatter) inherit from this base. Each agent has:
   - Tool binding via `register_tool()` and `call_tool()`
   - LLM integration through LiteLLM (`llm_generate()`)
   - Resilience patterns (circuit breaker, exponential backoff)
   - Memory management (short-term and Firestore-backed)

2. **LLM Integration**: All LLM calls go through LiteLLM. Model aliases are defined in `litellm_config.yaml` at the project root. Agent-specific aliases (e.g., `analyst-agent`, `planner-agent`) map to appropriate models with fallbacks configured.

3. **Resilience Layer**: The `resilience/` module provides:
   - `CircuitBreaker`: Prevents cascading failures (5 failures → open, 60s timeout)
   - `ExponentialBackoff`: Retry with jitter (1s initial, 60s max, 2x multiplier)

4. **A2A Protocol**: Inter-agent communication uses the Google A2A Protocol pattern. See `backend/app/agents/a2a/` for the message format and adapter implementation.

5. **Data Models**: Pydantic models in `backend/app/models/`. All models use snake_case for JSON serialization.

### Firestore Collections
- `payloads`: Stored payload templates
- `evidence_bundles`: Attack evidence and results
- `agent_memories`: Agent long-term memory

## Environment Variables

Required environment variables (set in `.env` or shell):
```
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GEMINI_API_KEY=your_gemini_key
FIREBASE_CREDENTIALS_PATH=path/to/serviceAccount.json  # Optional
GCP_PROJECT_ID=AgentTwister-dev  # Default
```

For local development with Firebase emulator:
```
FIRESTORE_EMULATOR_HOST=localhost:8080
```

## Security Research Scope

This tool is designed exclusively for:
- Authorized penetration testing
- Security research
- Red team exercises
- Compliance audits

All testing must be scoped, consented, and documented. See `docs/prd.md` for the complete product requirements.
