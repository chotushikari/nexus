# Tests

## Running

```bash
python -m pip install -e "apps/api[dev]"     # pytest, pytest-asyncio, httpx, fastapi, pydantic
python -m pytest                             # from the repo root
python -m pytest -m "not integration"        # explicit: skip credentialled tests
python tests/manual_verify.py                # stdlib-only checks, no dependencies needed
```

Configuration lives in the repo-root `pytest.ini` **only**. `apps/api/pyproject.toml`
must not reintroduce a `[tool.pytest.ini_options]` block: two configs made `pytest`
behave differently depending on the directory it was launched from.

`pytest.ini` collects `test_*.py`, `*_test.py` **and** `sprint_*.py`. It previously
collected only `sprint_*.py`, which silently excluded four suites.

## Layout

| File | Covers |
| --- | --- |
| `conftest.py` | dependency guards, per-test isolation of `store` / `capabilities` / `settings`, `client` / `live_client` fixtures, `poll_mission` helper |
| `test_planner_validation.py` | `plan_graph.validate_plan` against adversarial model output; `PlanSource.gemini` set only after successful validation |
| `test_policy_engine.py` | ALLOW / DENY / REQUIRE_APPROVAL; DENY not bypassable by retry or by a token; forged, mismatched and pending approval tokens |
| `test_mission_execution.py` | unique mission ids, async start, real layer concurrency, approval park/resume, circuit breakers, retries and skipped dependents |
| `test_persistence.py` | `json_store` round-trips, corrupt-file tolerance, `DualStore` read-through, a parked mission recovered after a simulated restart |
| `test_security_block.py` | prompt-injection detection, `SECURITY_ALERT` + `POLICY_BLOCKED`, and that injected instructions change nothing |
| `test_capabilities.py` | honest degradation: `deterministic_fallback`, `planModel is None`, `/api/health` reporting `gemini/adk/firestore = false` with reasons |
| `test_api_contracts.py` | HTTP status codes and shapes, `202 Accepted` for `POST /api/missions`, ad-hoc invoke still policy-gated, SSE stream |
| `test_e2e_mission.py` | the full operator walkthrough over HTTP: start, park, grant, complete, audit |
| `test_agent_registry.py` | roster size/tiers, identity scopes, tool ownership, capability mappings |
| `sprint_backend.py` | service-layer smoke suite (the retained copy; `sprint1_backend.py` was a byte-identical duplicate and was deleted) |
| `sprint_cloud_contracts.py` | the dataset the API actually resolves (`storage.DATA_DIR`), Firestore collection contract, data-tree drift |
| `sprint_google_stack.py` | SDK presence reported honestly; real-SDK assertions marked `integration` |
| `manual_verify.py` | stdlib-only runner: collection config, duplicates, syntax, dataset consistency, static defect confirmation |

## Rules

- **No network.** The Gemini transport is replaced by patching
  `planner._build_client` / `planner._generate`. Nothing in the default run
  reaches out.
- **Credentials.** Anything that genuinely needs them is `@pytest.mark.integration`
  and skips when absent. The marker is registered in `pytest.ini`.
- **Isolation.** The autouse `reset_runtime` fixture points the durable store at a
  per-test `tmp_path`, clears the capability registry, and forces Gemini
  credentials absent — so the default posture under test is the honest
  no-credentials posture, and one test's mocked success cannot make another pass.
- **Async missions.** `start_mission` returns immediately. Service-layer tests
  await `mission_service.wait_for_mission(id, timeout)`; HTTP tests use
  `poll_mission(client, id)` because the background task lives on the
  `TestClient` portal's event loop, not the test's.
- **`xfail` means a reported production defect.** Two tests in
  `test_persistence.py` and one check in `sprint_cloud_contracts.py` are `xfail`
  with the defect described in the reason. They flip to `XPASS` when fixed.
