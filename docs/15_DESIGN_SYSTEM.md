# NEXUS — DESIGN SYSTEM

## Visual Direction

Premium enterprise technology.

Style:

* sophisticated
* clean
* cinematic
* isometric
* information-dense
* restrained
* professional

Avoid:

* childish cartoon aesthetics
* generic SaaS dashboards
* excessive neon
* excessive animation
* game-like UI
* distracting particle effects

---

# Office

Use an isometric or 2.5D perspective.

The office should feel like a functioning enterprise headquarters.

---

# Departments

Each department should have:

* recognizable visual identity
* desks
* agent workstations
* status indicators
* department label

---

# Agent

Each agent should have:

* avatar
* name
* role
* department
* current status

Status should be visually obvious.

States:

IDLE
WORKING
COMMUNICATING
WAITING
APPROVAL_REQUIRED
BLOCKED
COMPLETED

---

# Security

Security events should be visually prominent but not overwhelming.

Use:

* alert indicator
* event panel
* affected agent
* action
* policy
* decision

---

# Operator UI

Primary navigation:

* Enterprise
* Missions
* Agents
* Departments
* Security
* Approvals
* Observability

---

# Agent Inspector

Right-side or modal inspector.

Information hierarchy:

1. identity
2. current activity
3. mission
4. permissions
5. tools
6. memory
7. events

---

# Mission Timeline

Chronological.

Example:

```text
10:41 Research started
10:42 Company search completed
10:43 Research → Compliance
10:44 Compliance policy check
10:45 Finance analysis
10:46 Restricted action blocked
10:47 Approval requested
10:48 Approved
10:49 Procurement completed
```

---

# Visual Principle

Animations must communicate information.

Do not animate simply because animation is possible.

Every movement should answer:

> What just happened?

---

# Scalability

The office must remain understandable as departments increase.

Use:

* zoom
* pan
* floor navigation
* department filtering
* agent search
* mission focus mode

These are enhancement features after the initial Track 3 implementation.
