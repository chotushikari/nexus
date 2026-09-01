# GOOGLE CLOUD STACK

## Required

### Gemini

Use Gemini 3.5+.

Prefer Flash for normal agent operations to control cost.

---

# Google ADK

Use Google Agent Development Kit as the primary agent framework.

ADK is responsible for:

* agent definitions
* orchestration
* tools
* sessions/state where applicable
* execution

---

# Cloud Run

Deploy backend services on Cloud Run.

Preferred characteristics:

* scale to zero
* small resource allocation
* maximum instance cap
* authenticated/protected endpoints where required

---

# Firestore

Use Firestore for:

* enterprise configuration
* agents
* departments
* missions
* tasks
* events
* approvals
* persistent state
* memory metadata

---

# Pub/Sub

Use if it materially improves asynchronous event handling.

Do not introduce it merely to make the architecture diagram look impressive.

---

# Cloud Logging

Use for backend logs and operational diagnostics.

---

# Cloud Trace / OpenTelemetry

Use where practical for execution tracing.

---

# Cloud Storage

Use for synthetic documents if required.

---

# Model Armor

Use where practical for prompt-injection/security inspection.

If not integrated, do not claim that NEXUS uses Model Armor.

Instead document the implemented security equivalent.

---

# Gemini Enterprise Agent Platform

Use actual managed GEAP capabilities if they are accessible and stable within the remaining implementation time.

Potential capabilities:

* Agent Registry
* Agent Runtime
* Memory Bank
* Agent Identity
* Agent Gateway
* Model Armor
* Agent Observability

Do not sacrifice the working Track 3 vertical slice because of an unstable optional integration.

---

# Cost Controls

Development should use:

* Gemini Flash/Flash-Lite where appropriate
* Cloud Run scale-to-zero
* low resource limits
* bounded agent iterations
* bounded tool calls
* synthetic data
* budget alerts

After the final recording:

* stop unused services
* delete unnecessary resources
* remove unnecessary deployments
