# NEXUS — SYSTEM ARCHITECTURE

## High-Level Architecture

```text
                         HUMAN OPERATOR
                                |
                                v
                       NEXUS WEB APPLICATION
                                |
                     Visual Enterprise Office
                                |
                                v
                         API / EVENT LAYER
                                |
                                v
                       OPERATIONS ORCHESTRATOR
                                |
             +------------------+------------------+
             |                  |                  |
             v                  v                  v
        RESEARCH           COMPLIANCE          FINANCE
          AGENT               AGENT              AGENT
             |                  |                  |
             +------------------+------------------+
                                |
                                v
                         PROCUREMENT AGENT
                                |
                                v
                       POLICY / GATEWAY LAYER
                                |
              +-----------------+----------------+
              |                 |                |
              v                 v                v
          IDENTITY          SECURITY          APPROVAL
              |                 |                |
              +-----------------+----------------+
                                |
                                v
                         DATA / MEMORY
                                |
                                v
                           EVENT STORE
                                |
                                v
                          OBSERVABILITY
```

---

# Frontend

Recommended:

* Next.js
* React
* TypeScript
* PixiJS

Responsibilities:

* render enterprise
* render departments
* render agents
* visualize events
* agent inspector
* mission timeline
* security center
* approvals
* registry
* control room

Frontend must not contain business authorization logic.

---

# Backend

Recommended:

* Python
* FastAPI
* Google ADK
* Gemini

Responsibilities:

* mission management
* orchestration
* agent execution
* tool execution
* policy evaluation
* persistence
* event generation
* approvals

---

# Google Cloud

Initial:

* Cloud Run
* Firestore

Potential:

* Pub/Sub
* Cloud Logging
* Cloud Trace
* Cloud Storage
* Model Armor
* Gemini Enterprise Agent Platform capabilities

---

# Data Model

```text
Enterprise
  |
  +-- Departments
        |
        +-- Agents
              |
              +-- Capabilities
              +-- Tools
              +-- Permissions
              +-- Policies
```

---

# Event-Driven UI

The backend produces events.

The event stream is consumed by the frontend.

Example:

```text
Agent
  |
  v
TOOL_STARTED
  |
  v
Event Store
  |
  +------> Observability
  |
  +------> Visual Office
```

---

# Critical Principle

The office must not independently invent agent behavior.

The backend is authoritative.

The visual layer interprets backend events.
