# NEXUS — READ FIRST

## Project

**NEXUS** is an autonomous enterprise operating environment for the All Things Agentic Hackathon — Fortified Enterprise Fleet track.

The central product idea:

> An enterprise where autonomous AI agents work like an organization, while a human operator can visually observe, inspect, govern, approve, deny, pause and audit their work.

The enterprise is represented as a living, expandable office.

The office is NOT a fake simulation.

The office is a visual projection of actual backend agent events.

---

# NON-NEGOTIABLE PRINCIPLES

## 1. Backend before visuals

The autonomous agent system must work before significant effort is spent on visual polish.

Priority:

P0 → functional agent system
P1 → governance/security/observability
P2 → visual office
P3 → expansion/polish

---

## 2. Never fake agent activity

If the office shows:

* an agent working
* an agent communicating
* a tool call
* a security alert
* an approval
* a mission completion

then the corresponding backend event must actually exist.

The frontend visualizes real events.

---

## 3. Google technology must be genuinely used

The project must genuinely use:

* Gemini 3.5 or newer
* Google ADK
* at least one Google Cloud service

Do not claim a Google product was used unless the implementation actually uses it.

---

## 4. Build Track 3 first

The first working vertical slice must demonstrate:

User mission
→ orchestrator
→ specialized agents
→ tools
→ persistence
→ policy
→ security
→ human approval
→ completion
→ audit trail

---

## 5. Use synthetic enterprise data

Do not use real confidential enterprise data.

Use synthetic:

* companies
* financial information
* contracts
* policies
* vendor documents
* identities

---

# CORE DEMO

The primary demo mission is:

> "Evaluate ACME Technologies and onboard them if they satisfy enterprise policies."

Agents:

1. Operations Orchestrator
2. Research Agent
3. Finance Agent
4. Compliance Agent
5. Procurement Agent

---

# VISUAL ENTERPRISE

Initial departments:

* Executive Office
* Research
* Finance
* Compliance
* Procurement
* Security Center
* Data / Memory Center
* Meeting Room

The architecture must support adding departments and agents dynamically later.

Departments and agents must come from data/configuration rather than being hard-coded into the rendering engine.

---

# IMPLEMENTATION RULE

At the beginning of every implementation phase:

1. Read the relevant documentation.
2. Inspect the existing code.
3. Identify dependencies.
4. Implement the smallest working change.
5. Run tests.
6. Run the application.
7. Verify behavior.
8. Update documentation.
9. Only then proceed.

Do not implement future phases prematurely.

---

# WHEN UNCERTAIN

Prefer:

1. official hackathon requirements
2. official Google documentation
3. repository documentation
4. tests/evidence from the existing implementation
5. reasonable engineering judgment

Never invent a requirement.

Never claim functionality without evidence.

---

# IMPORTANT

NEXUS is intended to be an original product.

Open-source projects may be used for acceleration, inspiration, or compatible components, but licenses must be verified and attribution requirements preserved.

See:

`12_OPEN_SOURCE_DISCLOSURE.md`

---

# REQUIRED DEVELOPMENT ORDER

1. Requirements
2. Repository architecture
3. Data model
4. ADK agent skeleton
5. Real tools
6. Multi-agent orchestration
7. Persistent state
8. Event system
9. Policy engine
10. Human approval
11. Security
12. Observability
13. Cloud deployment
14. Visual office
15. Agent inspector
16. Demo mode
17. Enterprise expansion
18. Final audit
