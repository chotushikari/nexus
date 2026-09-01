# ENTERPRISE MODEL

NEXUS must be designed as a configurable enterprise rather than a hard-coded office.

## Hierarchy

```text
Enterprise
    |
    +-- Department
          |
          +-- Agent
                |
                +-- Capabilities
                +-- Tools
                +-- Data Scopes
                +-- Policies
```

---

# Enterprise

```text
{
  id,
  name,
  description,
  createdAt,
  status
}
```

---

# Department

```text
{
  id,
  enterpriseId,
  name,
  description,
  managerAgentId,
  location,
  status
}
```

---

# Agent

```text
{
  id,
  departmentId,
  name,
  role,
  version,
  owner,
  identity,
  capabilities,
  tools,
  dataScopes,
  policies,
  riskLevel,
  status
}
```

---

# Dynamic Expansion

Eventually support:

```text
+ Add Department
+ Add Agent
+ Add Tool
+ Add Policy
```

The frontend must query configuration and render it.

Avoid:

```typescript
if department === "finance"
```

as the fundamental rendering architecture.

Prefer:

```text
departments.map(renderDepartment)
```

and:

```text
agents.map(renderAgent)
```

---

# Physical Office Mapping

Departments have:

* building/floor
* position
* size
* theme
* manager

Agents have:

* workstation
* position
* department
* status

The visual engine converts organizational data into physical representation.

---

# Scaling Vision

Initial:

5 agents / 8 rooms.

Future:

50+ agents / many departments.

The underlying schema should not need redesign to support this.
