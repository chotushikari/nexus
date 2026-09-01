# NEXUS Build Sprints

This document turns the architecture and roster into an implementation cadence. Attached documents are treated as design inputs; user requests and the repository docs remain the active source of execution decisions.

## Sprint 0 - Foundation

Goal: create the project structure, safety files, dependency manifests, synthetic data folders, and the 20-agent roster seed source.

Exit criteria:
- Repository has backend, frontend, infrastructure, data, scripts, packages, tests, and agents folders.
- Secrets are excluded by default.
- Environment variables are documented in `.env.local.example`.
- The 20-agent roster is represented as data, with tiers clearly separated.

## Sprint 1 - P0 Backend Vertical Slice

Goal: prove the mission works without the visual office.

Build:
- FastAPI mission endpoints
- five Tier 1 ADK agents
- synthetic tools
- event bus
- in-memory development repository with a Firestore-compatible interface
- policy gateway
- approval pause/resume
- audit endpoint

Exit criteria:
- `POST /api/demo/seed`
- `POST /api/missions`
- mission pauses on approval
- approval resumes mission
- audit trail reconstructs the mission
- tests pass

## Sprint 2 - Firestore Persistence

Goal: replace development storage with Firestore-backed mission, event, approval, agent, policy, and memory persistence.

Access needed:
- Google Cloud project ID
- Firestore database name
- local ADC or service account available on the machine, not pasted into chat

## Sprint 3 - Governance, Registry, And Security

Goal: deepen Track 3 evidence.

Build:
- complete agent registry endpoints
- identity and capability checks
- Tier 2 stub agents
- prompt-injection detection
- quarantine metadata
- security alert API
- circuit breaker

## Sprint 4 - Minimal Operator UI

Goal: show the real system without visual-office complexity.

Build:
- mission launcher
- event timeline
- approval cards
- agent inspector
- registry view with all 20 agents

## Sprint 5 - Visual Office

Goal: build the event-driven office on top of working backend evidence.

Build:
- PixiJS office engine
- data-driven departments and workstations
- event-to-visual state mapping
- no fake animation track

## Sprint 6 - Cloud Deployment

Goal: deploy the working system.

Build:
- Cloud Run backend deployment
- Firestore indexes/rules deployment
- frontend deployment
- Secret Manager wiring
- Cloud Logging proof

## Sprint 7 - Submission Audit

Goal: hostile judge audit.

Check every claim against:
- code evidence
- running-system evidence
- demo evidence
- documentation evidence

