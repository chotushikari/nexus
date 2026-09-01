# EVENT AND OBSERVABILITY SPECIFICATION

## Purpose

Events are the bridge between the real agent system and the visual office.

---

# Event Schema

```json
{
  "id": "",
  "type": "",
  "timestamp": "",
  "missionId": "",
  "agentId": "",
  "targetAgentId": "",
  "summary": "",
  "metadata": {}
}
```

---

# Event Types

```text
MISSION_CREATED
PLAN_CREATED

AGENT_STARTED
AGENT_WAITING
AGENT_COMPLETED
AGENT_FAILED
AGENT_PAUSED
AGENT_RESUMED

TOOL_STARTED
TOOL_COMPLETED
TOOL_FAILED

AGENT_MESSAGE

MEMORY_READ
MEMORY_WRITE

POLICY_CHECK
POLICY_ALLOWED
POLICY_BLOCKED

APPROVAL_REQUESTED
APPROVAL_GRANTED
APPROVAL_DENIED

SECURITY_ALERT

MISSION_PAUSED
MISSION_RESUMED
MISSION_COMPLETED
MISSION_FAILED
```

---

# Event Rules

Important state changes MUST create events.

Events must be persisted.

Events must be queryable by:

* mission
* agent
* event type
* timestamp

---

# Visual Mapping

```text
AGENT_STARTED
→ agent becomes active

TOOL_STARTED
→ tool activity indicator

AGENT_MESSAGE
→ communication animation

POLICY_BLOCKED
→ security alert

APPROVAL_REQUESTED
→ agent escalates

APPROVAL_GRANTED
→ agent resumes

AGENT_COMPLETED
→ completion state

MISSION_COMPLETED
→ mission completion visualization
```

---

# Observability UI

Show:

* active missions
* active agents
* recent events
* tool calls
* policy decisions
* security events
* approvals
* failures

---

# Agent Inspector

For selected agent:

```text
Identity
Role
Department
Version
Status

Current Mission
Current Task

Tools
Permissions
Data Scopes

Memory Summary

Recent Events
Recent Communications
Policy Decisions
```

---

# Audit Trail

A mission should be reconstructable entirely from stored events.

Do not rely on frontend-only state.
