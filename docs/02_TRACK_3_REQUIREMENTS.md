# TRACK 3 — FORTIFIED ENTERPRISE FLEET

## Capability Matrix

| Capability                | NEXUS Implementation                    | Evidence              |
| ------------------------- | --------------------------------------- | --------------------- |
| Agent discovery           | Agent Registry                          | Registry UI           |
| Agent versioning          | Agent metadata                          | Agent Inspector       |
| Multi-agent orchestration | Google ADK orchestrator                 | Live mission          |
| Specialized agents        | Research/Finance/Compliance/Procurement | Mission               |
| Long-running execution    | Persistent mission state                | Resume test           |
| Persistent memory         | Firestore-backed state/memory           | Memory UI             |
| Agent identity            | Agent identity + scopes                 | Inspector             |
| Authorization             | Policy engine                           | Allow/deny            |
| Gateway                   | Central tool authorization layer        | Tool request          |
| Security                  | Prompt injection defense                | Security demo         |
| Human governance          | Approval workflow                       | Executive Office      |
| Observability             | Event stream/audit trail                | Control Room          |
| Failure handling          | Circuit breaker/retry/state recovery    | Test/demo             |
| Cloud deployment          | Cloud Run                               | Public deployment     |
| Google agent framework    | ADK                                     | Repository/code       |
| Gemini                    | Gemini 3.5+                             | Runtime configuration |

---

# P0 — REQUIRED

## Multi-Agent System

At minimum:

* Operations Orchestrator
* Research Agent
* Finance Agent
* Compliance Agent
* Procurement Agent

Agents must have differentiated responsibilities.

---

# P0 — REAL TOOL USAGE

Agents must perform actual tool calls.

Examples:

Research:

* company search
* document retrieval

Finance:

* financial lookup
* risk calculation

Compliance:

* policy search
* compliance check

Procurement:

* supplier scoring
* contract drafting

Tools may initially use synthetic datasets.

---

# P0 — PERSISTENCE

Persist:

* mission
* task
* agent state
* messages
* decisions
* approvals
* events

The mission must survive frontend restart.

---

# P0 — GOVERNANCE

Every sensitive operation must pass through authorization.

Decision types:

ALLOW
DENY
REQUIRE_APPROVAL

---

# P0 — HUMAN CONTROL

The operator must be able to:

* approve
* deny
* pause
* resume
* inspect
* terminate where practical

---

# P1 — SECURITY

Demonstrate at least one realistic attack.

Primary attack:

Prompt injection embedded in a synthetic vendor document.

Expected result:

Document
→ security inspection
→ threat detected
→ malicious instruction rejected
→ security event recorded
→ mission continues safely

---

# P1 — OBSERVABILITY

Record:

* mission creation
* agent activation
* tool calls
* tool results
* agent messages
* memory access
* policy decisions
* security alerts
* approval requests
* approval outcomes
* mission completion

---

# P1 — AGENT REGISTRY

Each agent should expose:

* ID
* name
* role
* department
* version
* owner
* status
* capabilities
* tools
* data scopes
* identity
* risk level
* policies

---

# P2 — VISUALIZATION

Visualize actual events.

Examples:

AGENT_STARTED
→ agent becomes active

TOOL_STARTED
→ tool activity shown

AGENT_MESSAGE
→ message animation

POLICY_BLOCKED
→ security alert

APPROVAL_REQUESTED
→ agent escalates

APPROVAL_GRANTED
→ agent resumes

MISSION_COMPLETED
→ mission completion state

---

# P3 — SCALE

Architecture must eventually support:

* arbitrary departments
* arbitrary agents
* configurable tools
* configurable policies
* enterprise expansion

Do not hard-code the initial organization into the rendering engine.
