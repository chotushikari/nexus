# NEXUS

Autonomous Enterprise Operating Environment for the All Things Agentic Hackathon, Fortified Enterprise Fleet track.

NEXUS is built around one rule: the office is not a simulation. It is a visual projection of real backend agent events.

## Current Sprint

Sprint 0 sets up the project foundation only:

- Python/FastAPI backend workspace
- Google ADK and Gemini dependency plan
- Next.js frontend workspace
- Firestore/Cloud Run infrastructure folders
- synthetic data folders
- 20-agent roster seed structure
- safety files for credentials and deployment packaging

The P0 implementation comes next: mission creation, five core ADK agents, synthetic tools, policy gateway, approval pause/resume, Firestore persistence, and audit events.

## Repository Layout

```text
apps/
  api/        FastAPI backend and ADK host
  web/        Next.js operator interface
agents/       ADK agent definitions and prompts
packages/     shared schemas, events, policy, security, office engine
data/         synthetic enterprise data and agent cards
docs/         project source-of-truth documents
infrastructure/
  cloud-run/  Cloud Run deployment config
  firestore/  Firestore rules and indexes
  pubsub/     optional event fan-out config
scripts/      seed, demo, deploy, and shutdown helpers
tests/        backend and integration tests
```

## Required Access Later

Do not paste secrets into chat. When we reach the cloud sprint, provide only project names and confirm that credentials are stored locally or in Secret Manager.

- Google Cloud project ID
- Google Cloud region
- Gemini API key or Vertex/enterprise auth choice
- Firestore database name
- Cloud Run deployment permission
- Secret Manager access for runtime secrets

