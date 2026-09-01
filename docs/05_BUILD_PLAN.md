# NEXUS — BUILD PLAN

## Phase 0 — Project Setup

Create:

* repository
* documentation
* environment configuration
* linting
* testing
* Git structure

Do not build visual UI.

---

# Phase 1 — Data Model

Implement Firestore/data models:

* enterprises
* departments
* agents
* missions
* tasks
* messages
* events
* policies
* approvals
* tools
* memory

Ensure all IDs are stable.

---

# Phase 2 — ADK Foundation

Implement:

* Gemini configuration
* ADK project
* orchestrator
* agent base abstraction
* tool abstraction
* structured responses

Verify a single agent works.

---

# Phase 3 — Specialized Agents

Implement:

Research Agent
Finance Agent
Compliance Agent
Procurement Agent

Each agent must have:

* system instructions
* role
* capabilities
* tools
* permissions
* output schema

---

# Phase 4 — Real Orchestration

Implement:

mission creation
→ planning
→ delegation
→ agent execution
→ agent communication
→ dependency handling
→ completion

Do not use a hard-coded sequential script if ADK orchestration can make the decision dynamically.

---

# Phase 5 — Tools

Implement synthetic tools.

Research:

* company_search
* document_reader

Finance:

* financial_lookup
* risk_calculator

Compliance:

* policy_search
* compliance_check

Procurement:

* supplier_score
* contract_draft

---

# Phase 6 — Persistence

Persist:

* mission state
* task state
* agent state
* messages
* memory
* decisions

Test:

1. start mission
2. interrupt frontend
3. restart frontend
4. retrieve mission
5. continue execution

---

# Phase 7 — Event System

Create structured event schema.

Every important backend operation must generate an event.

Persist events.

Expose events to frontend.

---

# Phase 8 — Governance

Implement:

* Agent Registry
* identity
* permissions
* tool scopes
* data scopes
* policy engine
* gateway
* allow
* deny
* require approval

---

# Phase 9 — Human Approval

Implement:

approval request
→ UI notification
→ approve/deny
→ persisted decision
→ agent resumes or terminates

---

# Phase 10 — Security

Implement prompt-injection protection.

Create malicious synthetic document.

Block malicious instruction.

Create security event.

Integrate Model Armor if practical and available.

Do not falsely claim Model Armor if the actual implementation does not use it.

---

# Phase 11 — Observability

Implement:

* event timeline
* agent activity
* tool calls
* policy decisions
* security events
* approvals
* errors
* mission trace

---

# Phase 12 — Cloud

Deploy backend to Cloud Run.

Configure Firestore.

Configure required services.

Test public deployment.

---

# Phase 13 — Visual Office

Build:

* Executive Office
* Research
* Finance
* Compliance
* Procurement
* Security Center
* Data/Memory Center
* Meeting Room

Use generic data-driven components.

---

# Phase 14 — Agent Inspector

Click agent.

Show:

* identity
* role
* department
* status
* mission
* current task
* tools
* permissions
* memory
* recent activity
* policy decisions

---

# Phase 15 — Demo Mode

Create deterministic synthetic demo.

Critical path:

mission
→ research
→ compliance
→ finance
→ procurement
→ restricted action
→ block
→ approval
→ resume
→ completion

Demo must be reproducible.

---

# Phase 16 — Enterprise Expansion

Only after P0/P1/P2 works.

Implement:

* Add Department
* Add Agent
* Add Tool
* Add Policy

The visual office should automatically update.

---

# Phase 17 — Final Audit

Run:

* unit tests
* integration tests
* security tests
* persistence test
* cloud deployment test
* demo test

Then audit against Track 3.

---

# Development Rule

Never move to a later phase because a previous phase is "mostly working."

The critical vertical slice must be stable before visual polish.
