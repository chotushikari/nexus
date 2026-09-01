# DEFINITION OF DONE

NEXUS is not submission-ready until the following are true.

## Technology

* [ ] Gemini 3.5+ actually used
* [ ] Google ADK actually used
* [ ] Google Cloud service actually used
* [ ] Cloud deployment works

## Agents

* [ ] Orchestrator exists
* [ ] Research Agent exists
* [ ] Finance Agent exists
* [ ] Compliance Agent exists
* [ ] Procurement Agent exists
* [ ] Agents have differentiated responsibilities
* [ ] Agents can communicate

## Tools

* [ ] Agents perform actual tool calls
* [ ] Tool results affect agent behavior
* [ ] Tool permissions are enforced

## Persistence

* [ ] Mission state persists
* [ ] Agent state persists
* [ ] Messages persist
* [ ] Decisions persist
* [ ] Mission survives frontend restart

## Registry

* [ ] Agents discoverable
* [ ] Agent version stored
* [ ] Owner stored
* [ ] Capabilities stored
* [ ] Tools stored
* [ ] Data scopes stored
* [ ] Risk level stored

## Identity

* [ ] Every agent has identity
* [ ] Identity maps to permissions
* [ ] Different agents have different scopes

## Governance

* [ ] ALLOW exists
* [ ] DENY exists
* [ ] REQUIRE_APPROVAL exists
* [ ] Sensitive actions are governed
* [ ] Policy decisions are audited

## Human Control

* [ ] Approval request appears
* [ ] User can approve
* [ ] User can deny
* [ ] Agent reacts correctly

## Security

* [ ] Prompt injection scenario exists
* [ ] Attack is blocked
* [ ] Security event created
* [ ] Block appears in UI
* [ ] PII/tool risks are considered

## Observability

* [ ] Events generated
* [ ] Events persisted
* [ ] Mission timeline exists
* [ ] Agent activity inspectable
* [ ] Tool calls inspectable
* [ ] Policy decisions inspectable
* [ ] Security alerts inspectable

## Visual Office

* [ ] Departments render dynamically
* [ ] Agents render dynamically
* [ ] Agent status is visible
* [ ] Communication is visible
* [ ] Security alerts are visible
* [ ] Approval escalation is visible
* [ ] Completion is visible

## Demo

* [ ] Complete mission works
* [ ] Demo can be reproduced
* [ ] Demo fits within four minutes
* [ ] No fake backend activity
* [ ] Public deployment works

## Documentation

* [ ] README
* [ ] architecture
* [ ] deployment instructions
* [ ] open-source disclosure
* [ ] hackathon checklist
* [ ] demo script
