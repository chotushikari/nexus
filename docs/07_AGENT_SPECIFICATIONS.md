# AGENT SPECIFICATIONS

## 1. Operations Orchestrator

Role:

Enterprise Operations Manager

Responsibilities:

* receive mission
* create plan
* delegate
* track dependencies
* monitor progress
* handle failures
* request human intervention

Must NOT directly access all enterprise data.

---

# 2. Research Agent

Role:

Research Analyst

Responsibilities:

* investigate vendor
* retrieve company information
* analyze supplied documents
* provide research summary

Capabilities:

* company research
* document analysis

Example tools:

* company_search
* document_reader

Access:

* public/synthetic research data
* research-scoped documents

---

# 3. Compliance Agent

Role:

Compliance Officer

Responsibilities:

* evaluate enterprise policies
* review vendor documents
* identify violations
* produce compliance assessment

Tools:

* policy_search
* compliance_check

Access:

* policy data
* compliance data

---

# 4. Finance Agent

Role:

Financial Analyst

Responsibilities:

* assess financial risk
* calculate exposure
* review invoices
* provide financial recommendation

Tools:

* financial_lookup
* risk_calculator

Access:

* financial data

Explicit restrictions:

Finance MUST NOT have:

* bank.read
* payment.write

High-risk financial mutations require human approval.

---

# 5. Procurement Agent

Role:

Procurement Manager

Responsibilities:

* evaluate supplier recommendation
* prepare onboarding package
* draft contracts
* finalize procurement workflow where authorized

Tools:

* supplier_score
* contract_draft

---

# Agent Metadata

Every agent should have:

```json
{
  "id": "",
  "name": "",
  "role": "",
  "departmentId": "",
  "version": "",
  "owner": "",
  "status": "",
  "capabilities": [],
  "tools": [],
  "dataScopes": [],
  "identity": "",
  "riskLevel": "",
  "policies": []
}
```

---

# Agent Behavior Rule

Agents must not bypass:

* identity
* policy
* gateway
* security
* approval requirements

The orchestrator cannot override enterprise security policy merely because it requests an action.
