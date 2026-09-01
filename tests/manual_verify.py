#!/usr/bin/env python3
"""Standard-library-only verification runner for the NEXUS backend test suite.

WHY THIS FILE EXISTS
--------------------
The environment this suite was authored in had **no network egress and no pip
index**: `pytest`, `pydantic`, `fastapi` and `httpx` were all
`ModuleNotFoundError`, and `pip download pytest` failed with
`ProxyError / 403 Forbidden`. `python -m pytest` could not run, and essentially
every module under `apps/api/nexus_api/` imports `pydantic` (directly, or via
`nexus_api.schemas.domain` / `nexus_api.core.config`), so the backend could not
be imported either.

Rather than fake a pydantic shim — which would prove nothing about the real code
— this script verifies everything that *can* honestly be verified with the
standard library alone, and says plainly what it cannot verify.

WHAT IT CHECKS (all real, no reimplementation of production logic)
-----------------------------------------------------------------
  1. which third-party dependencies are importable in this interpreter;
  2. pytest collection configuration: every test file matches a `python_files`
     pattern, the `integration` marker is registered, and no second, conflicting
     pytest config exists in `apps/api/pyproject.toml`;
  3. no byte-identical duplicate files in `tests/`;
  4. no retired identifiers (`demo-mission-001`, `wayne-enterprises`,
     `acme-technologies`) left in `tests/`;
  5. every `.py` file under `apps/api/nexus_api/` and `tests/` parses (AST) —
     this is the syntax check the unrunnable pytest suite could not give us;
  6. test inventory: counts per file, duplicate test names (which silently
     shadow a test), and whether each module guards its imports so a missing
     dependency skips instead of erroring the whole run;
  7. production identity defaults read out of `core/config.py` by AST, so the
     `meridian-industrial` / `kestrel-components` change is confirmed without
     importing pydantic-settings;
  8. dataset consistency for the tree the API resolves: roster size/tiers/ids,
     tier-1 system prompts on disk, `tools.json` owners, department count, and
     the configured default vendor having a synthetic record;
  9. the bundled malicious vendor document really trips the injection pattern
     list, where the pattern list is extracted from `services/security.py` by
     AST rather than copied;
 10. static confirmation of the reported `json_store` read/write name asymmetry
     and of the approval-token verification checks.

WHAT IT CANNOT CHECK
--------------------
  * anything that requires executing the backend: policy evaluation, mission
    orchestration, concurrency, approval park/resume, circuit breakers,
    persistence round-trips, the FastAPI routes. Those are covered by the pytest
    files in this directory and need `pip install -e "apps/api[dev]"`.
  * any Gemini / ADK / Firestore behaviour.

USAGE
-----
    python tests/manual_verify.py            # from anywhere
    python tests/manual_verify.py --verbose

Exit code 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"
API_ROOT = REPO_ROOT / "apps" / "api"
NEXUS_API = API_ROOT / "nexus_api"

DEPENDENCIES = (
    "pytest",
    "pytest_asyncio",
    "pydantic",
    "pydantic_settings",
    "fastapi",
    "httpx",
    "starlette",
    "anyio",
    "google.genai",
    "google.adk",
    "google.cloud.firestore",
)

RETIRED_IDENTIFIERS = ("demo-mission-001", "wayne-enterprises", "acme-technologies")


# Directories that are never part of the Python project and can be huge or
# unreadable (the sandbox raises OSError walking some node_modules symlinks).
SKIP_DIRS = {
    "node_modules",
    ".git",
    ".next",
    "__pycache__",
    ".venv",
    "venv",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "dist",
    "build",
    ".nexus-state",
}


def _walk_py_project(root: Path, filename: str) -> list[Path]:
    """Find `filename` under `root`, skipping non-project directories."""
    import os

    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root, onerror=lambda _: None):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        if filename in filenames:
            found.append(Path(dirpath) / filename)
    return found


class Report:
    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.defects: list[str] = []
        self.notes: list[str] = []

    def section(self, title: str) -> None:
        print(f"\n{title}")
        print("-" * len(title))

    def ok(self, message: str) -> None:
        self.passed += 1
        if self.verbose:
            print(f"  PASS    {message}")

    def fail(self, message: str) -> None:
        self.failed += 1
        print(f"  FAIL    {message}")

    def skip(self, message: str) -> None:
        self.skipped += 1
        print(f"  SKIP    {message}")

    def defect(self, message: str) -> None:
        """A confirmed defect in *production* code.

        Reported loudly but counted separately from test-suite failures: this
        script's job is to verify the suite, not to gate on bugs it only reports.
        """
        self.defects.append(message)
        print(f"  DEFECT  {message}")

    def check(self, condition: bool, message: str) -> bool:
        if condition:
            self.ok(message)
        else:
            self.fail(message)
        return bool(condition)

    def info(self, message: str) -> None:
        print(f"  ..      {message}")

    def note(self, message: str) -> None:
        self.notes.append(message)


# ── 1. dependency availability ──────────────────────────────────────────────


def check_dependencies(report: Report) -> dict[str, bool]:
    report.section("1. Dependency availability in this interpreter")
    available: dict[str, bool] = {}
    for name in DEPENDENCIES:
        try:
            found = importlib.util.find_spec(name) is not None
        except (ImportError, ValueError, ModuleNotFoundError):
            found = False
        available[name] = found
        print(f"  {'present' if found else 'MISSING':>8}  {name}")
    if not available["pytest"]:
        report.note(
            "pytest is not installed here, so the pytest suite in tests/ was never executed. "
            "Run `python -m pip install -e \"apps/api[dev]\"` then `python -m pytest`."
        )
    if not available["pydantic"]:
        report.note(
            "pydantic is not installed here, so nexus_api cannot be imported and no backend "
            "behaviour below is executed — only static and data checks run."
        )
    return available


# ── 2. pytest collection configuration ──────────────────────────────────────


def parse_ini(path: Path) -> dict[str, str]:
    """Minimal INI reader (configparser would also work; this keeps multi-line
    values such as `markers` intact)."""
    values: dict[str, str] = {}
    key: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith(("#", ";", "[")):
            continue
        if "=" in line and not line.startswith((" ", "\t")):
            key, _, value = line.partition("=")
            key = key.strip()
            values[key] = value.strip()
        elif key is not None:
            values[key] = f"{values.get(key, '')}\n{line.strip()}".strip()
    return values


def check_pytest_config(report: Report) -> None:
    report.section("2. pytest collection configuration")
    ini_path = REPO_ROOT / "pytest.ini"
    if not report.check(ini_path.is_file(), "pytest.ini exists"):
        return
    config = parse_ini(ini_path)

    patterns = config.get("python_files", "test_*.py").split()
    report.info(f"python_files = {' '.join(patterns)}")

    test_files = sorted(
        path
        for path in TESTS_DIR.glob("*.py")
        if path.name not in {"conftest.py", "manual_verify.py", "__init__.py"}
    )
    uncollected = [
        path.name
        for path in test_files
        if not any(fnmatch.fnmatch(path.name, pattern) for pattern in patterns)
    ]
    report.check(
        not uncollected,
        f"every test file matches a python_files pattern (uncollected: {uncollected})",
    )
    report.check(
        any(fnmatch.fnmatch("test_example.py", pattern) for pattern in patterns),
        "the `test_*.py` convention is collected (the original bug: `sprint_*.py` only)",
    )
    report.check(
        any(fnmatch.fnmatch("sprint_example.py", pattern) for pattern in patterns),
        "the legacy `sprint_*.py` convention is still collected",
    )
    report.check(
        "integration" in config.get("markers", ""),
        "the `integration` marker is registered (no PytestUnknownMarkWarning)",
    )
    report.check(
        config.get("asyncio_mode", "") == "auto",
        "asyncio_mode = auto, so bare `async def test_*` functions run",
    )
    report.check("testpaths" in config, "testpaths is set in pytest.ini")

    pyproject = API_ROOT / "pyproject.toml"
    if pyproject.is_file():
        # Look for a real TOML section header, not the explanatory comment that
        # records why the block was removed.
        headers = [
            line.strip()
            for line in pyproject.read_text(encoding="utf-8").splitlines()
            if line.strip().startswith("[tool.pytest")
        ]
        report.check(
            not headers,
            f"apps/api/pyproject.toml declares no second, conflicting pytest config ({headers})",
        )
    else:
        report.skip("apps/api/pyproject.toml not found")

    extras = [
        path
        for path in _walk_py_project(REPO_ROOT, "pytest.ini")
        if path != ini_path
    ]
    report.check(not extras, f"exactly one pytest.ini in the repo (extras: {extras})")
    for name in ("setup.cfg", "tox.ini"):
        for path in _walk_py_project(REPO_ROOT, name):
            if "[pytest]" in path.read_text(encoding="utf-8", errors="replace"):
                report.fail(f"{path} also declares a [pytest] section")


# ── 3. duplicate files ──────────────────────────────────────────────────────


def check_no_duplicate_test_files(report: Report) -> None:
    report.section("3. Duplicate test files")
    digests: dict[str, list[str]] = {}
    for path in sorted(TESTS_DIR.glob("*.py")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        digests.setdefault(digest, []).append(path.name)
    duplicates = {digest: names for digest, names in digests.items() if len(names) > 1}
    report.check(not duplicates, f"no byte-identical duplicates in tests/ ({duplicates})")


# ── 4. retired identifiers ──────────────────────────────────────────────────


def _docstring_constants(tree: ast.Module) -> set[int]:
    """`id()` of every string Constant node used as a docstring."""
    found: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            found.add(id(body[0].value))
    return found


def check_retired_identifiers(report: Report) -> None:
    report.section("4. Retired identifiers in tests/")
    offenders: list[str] = []
    negatives = 0
    for path in sorted(TESTS_DIR.glob("*.py")):
        if path.name == "manual_verify.py":
            continue  # this file names them on purpose
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        tree = ast.parse(source, filename=str(path))
        docstrings = _docstring_constants(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if id(node) in docstrings:
                continue  # prose explaining the change is fine
            if not any(identifier in node.value for identifier in RETIRED_IDENTIFIERS):
                continue
            line = lines[node.lineno - 1] if node.lineno <= len(lines) else ""
            # `!=` / `not in` assert the value is absent; `404` asserts the old
            # id is unresolvable. Both are exactly what we want to see.
            if "!=" in line or "not in" in line or "404" in line:
                negatives += 1
                continue
            offenders.append(f"{path.name}:{node.lineno}: {line.strip()[:90]}")

    report.check(
        not offenders,
        "no test asserts the retired demo identity as a live value "
        f"(offenders: {len(offenders)})",
    )
    for offender in offenders:
        report.info(offender)
    report.info(
        f"{negatives} assertion(s) explicitly check a retired identifier is NOT used"
    )
    report.check(
        negatives >= 3,
        "the suite actively asserts the retired identifiers are gone "
        f"(found {negatives} negative assertions)",
    )


# ── 5. syntax check ─────────────────────────────────────────────────────────


def check_syntax(report: Report) -> None:
    report.section("5. Syntax check (AST parse)")
    roots = [("apps/api/nexus_api", NEXUS_API), ("tests", TESTS_DIR)]
    for label, root in roots:
        if not root.is_dir():
            report.skip(f"{label} not found")
            continue
        files = sorted(root.rglob("*.py"))
        bad: list[str] = []
        for path in files:
            if "__pycache__" in path.parts:
                continue
            try:
                ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except SyntaxError as exc:
                bad.append(f"{path.relative_to(REPO_ROOT)}:{exc.lineno}: {exc.msg}")
        report.check(not bad, f"{label}: all {len(files)} files parse")
        for entry in bad:
            report.info(entry)


# ── 6. test inventory ───────────────────────────────────────────────────────


def _test_functions(tree: ast.Module) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
            "test_"
        ):
            names.append(node.name)
    return names


def check_test_inventory(report: Report) -> None:
    report.section("6. Test inventory")
    total = 0
    guard_missing: list[str] = []
    for path in sorted(TESTS_DIR.glob("*.py")):
        if path.name in {"conftest.py", "manual_verify.py"}:
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        names = _test_functions(tree)
        total += len(names)
        duplicates = sorted({name for name in names if names.count(name) > 1})
        report.check(
            not duplicates,
            f"{path.name}: no duplicated test names ({duplicates})",
        )
        if "requires_backend()" not in source and "requires_api()" not in source:
            guard_missing.append(path.name)
        print(f"  {len(names):>4} tests  {path.name}")
    report.check(
        not guard_missing,
        "every test module calls requires_backend()/requires_api() so a missing "
        f"dependency skips rather than erroring collection (missing: {guard_missing})",
    )
    report.info(f"{total} test functions declared (before parametrisation)")
    report.note(
        f"{total} test functions are declared across tests/; parametrisation expands this "
        "further. None of them were executed in the authoring sandbox."
    )


# ── 7. production identity defaults (AST, no pydantic) ──────────────────────


def _assignment_defaults(path: Path, class_name: str) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            values: dict[str, object] = {}
            for statement in node.body:
                if isinstance(statement, ast.AnnAssign) and isinstance(
                    statement.target, ast.Name
                ):
                    try:
                        values[statement.target.id] = ast.literal_eval(statement.value)
                    except (ValueError, TypeError):
                        continue
            return values
    return {}


def check_identity_defaults(report: Report) -> dict[str, object]:
    report.section("7. Configured identity defaults (read from config.py by AST)")
    config_path = NEXUS_API / "core" / "config.py"
    if not config_path.is_file():
        report.skip("core/config.py not found")
        return {}
    defaults = _assignment_defaults(config_path, "Settings")
    expected = {
        "enterprise_id": "meridian-industrial",
        "enterprise_name": "Meridian Industrial",
        "default_vendor_id": "kestrel-components",
        "default_vendor_name": "Kestrel Components",
    }
    for key, value in expected.items():
        report.check(defaults.get(key) == value, f"Settings.{key} == {value!r} (got {defaults.get(key)!r})")
    report.check(
        defaults.get("gemini_model") is None,
        "gemini_model default is a module constant, not an inline literal",
    )
    return defaults


# ── 8. dataset consistency ──────────────────────────────────────────────────

# Transcribed from `services/storage.py::find_project_root` / REQUIRED_DATA_FILES
# so the *resolved* dataset can be located without importing pydantic. Flagged
# explicitly as a transcription: if storage.py's resolution rule changes, this
# must change with it.
REQUIRED_DATA_FILES = ("agents/roster.json", "departments.json")


def resolve_data_dir() -> Path:
    storage_py = NEXUS_API / "services" / "storage.py"
    candidates = [storage_py, *storage_py.parents]
    for parent in candidates:
        candidate = parent / "data"
        if all((candidate / relative).is_file() for relative in REQUIRED_DATA_FILES):
            return candidate
    for parent in candidates:
        if (parent / "data").exists():
            return parent / "data"
    return REPO_ROOT / "data"


def check_dataset(report: Report, defaults: dict[str, object]) -> Path:
    report.section("8. Dataset the API resolves")
    data_dir = resolve_data_dir()
    report.info(f"resolved data dir: {data_dir}")
    if data_dir != REPO_ROOT / "data":
        report.note(
            f"the API resolves its dataset to {data_dir}, NOT <repo>/data. Both trees exist and "
            "must stay identical or they will drift."
        )

    roster_path = data_dir / "agents" / "roster.json"
    if not report.check(roster_path.is_file(), f"{roster_path} exists"):
        return data_dir
    roster = json.loads(roster_path.read_text(encoding="utf-8"))["agents"]
    report.check(len(roster) == 20, f"roster has 20 agents (got {len(roster)})")
    report.check(
        {agent["tier"] for agent in roster} == {1, 2, 3}, "roster spans tiers 1, 2 and 3"
    )
    ids = [agent["id"] for agent in roster]
    report.check(len(set(ids)) == len(ids), "roster agent ids are unique")

    tier_one = [agent for agent in roster if agent["tier"] == 1]
    report.check(len(tier_one) == 5, f"five tier-1 agents (got {len(tier_one)})")
    for agent in tier_one:
        prompt = REPO_ROOT / agent["systemPromptPath"]
        report.check(
            prompt.is_file() and bool(prompt.read_text(encoding="utf-8").strip()),
            f"{agent['id']} system prompt readable at {agent['systemPromptPath']}",
        )

    departments_path = data_dir / "departments.json"
    departments = json.loads(departments_path.read_text(encoding="utf-8"))
    report.check(len(departments) >= 12, f"at least 12 departments (got {len(departments)})")
    report.check(
        all("location" in item and "theme" in item for item in departments),
        "every department carries a location and a theme",
    )

    tools_path = data_dir / "tools.json"
    if tools_path.is_file():
        catalogue = json.loads(tools_path.read_text(encoding="utf-8"))
        unknown = [tool["id"] for tool in catalogue if tool.get("ownerAgentId") not in set(ids)]
        report.check(not unknown, f"every tool has a real owner agent (orphans: {unknown})")
        gated = {tool["id"] for tool in catalogue if tool.get("requiresApproval")}
        report.check(
            {"create_payment", "contract_finalize"} <= gated,
            f"the high-risk tools are flagged requiresApproval (got {sorted(gated)})",
        )
    else:
        report.skip("tools.json not found")

    vendor_id = defaults.get("default_vendor_id")
    vendors_path = data_dir / "synthetic" / "vendors.json"
    if vendors_path.is_file() and vendor_id:
        vendors = json.loads(vendors_path.read_text(encoding="utf-8"))
        report.check(
            vendor_id in vendors,
            f"the configured default vendor {vendor_id!r} has a synthetic record",
        )
    else:
        report.skip("synthetic/vendors.json not found")

    # Drift between the two data trees.
    other = REPO_ROOT / "data" if data_dir != REPO_ROOT / "data" else API_ROOT / "data"
    if other.is_dir():
        drifted = []
        for relative in (
            "agents/roster.json",
            "departments.json",
            "tools.json",
            "synthetic/vendors.json",
        ):
            left, right = data_dir / relative, other / relative
            if left.is_file() and right.is_file():
                if json.loads(left.read_text(encoding="utf-8")) != json.loads(
                    right.read_text(encoding="utf-8")
                ):
                    drifted.append(relative)
        report.check(not drifted, f"the two data trees agree (drifted: {drifted})")
    return data_dir


# ── 9. prompt-injection fixture ─────────────────────────────────────────────


def _literal_list(path: Path, name: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                value = ast.literal_eval(node.value)
                return list(value)
    raise KeyError(name)


def check_prompt_injection_fixture(report: Report, data_dir: Path) -> None:
    report.section("9. Prompt-injection fixture vs the real pattern list")
    security_py = NEXUS_API / "services" / "security.py"
    try:
        patterns = _literal_list(security_py, "PROMPT_INJECTION_PATTERNS")
    except (KeyError, ValueError, SyntaxError) as exc:
        report.fail(f"could not read PROMPT_INJECTION_PATTERNS from security.py: {exc}")
        return
    report.info(f"{len(patterns)} patterns declared in services/security.py")
    report.check(bool(patterns), "the pattern list is not empty")

    document = data_dir / "synthetic" / "malicious_vendor_document.txt"
    if not report.check(document.is_file(), f"{document} exists"):
        return
    text = document.read_text(encoding="utf-8").lower()
    # NOTE: `pattern in text.lower()` is the one line of production logic
    # transcribed here (services/security.py). Everything else is the real data.
    matched = [pattern for pattern in patterns if pattern in text]
    report.check(
        len(matched) >= 3,
        f"the bundled document trips >= 3 injection patterns (matched {len(matched)}: {matched})",
    )

    clean = "KESTREL COMPONENTS LTD.\nRegistration: ROC-KC-2019-004417\nEmployees: 640\n".lower()
    report.check(
        not [pattern for pattern in patterns if pattern in clean],
        "a clean vendor report trips no pattern (the scanner is not always-true)",
    )


# ── 10. static confirmation of reported defects ─────────────────────────────


def _function_source(path: Path, name: str, class_name: str | None = None) -> str:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    scopes: list[ast.AST] = [tree]
    if class_name:
        scopes = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == class_name
        ]
    for scope in scopes:
        for node in ast.walk(scope):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
                return ast.get_source_segment(source, node) or ""
    return ""


def check_reported_defects(report: Report) -> None:
    report.section("10. Static confirmation of reported production issues")
    json_store = NEXUS_API / "services" / "json_store.py"
    save_mission = _function_source(json_store, "save_mission", "JsonFileStore")
    get_mission = _function_source(json_store, "get_mission", "JsonFileStore")
    if save_mission and get_mission:
        writes_sanitised = "_safe_name" in save_mission
        reads_sanitised = "_safe_name" in get_mission
        if reads_sanitised and not writes_sanitised:
            report.defect(
                "JsonFileStore.get_mission sanitises the id with _safe_name() but save_mission "
                "writes the raw id, so the two disagree for any id containing a rewritten "
                "character, and the write path does not confine the file to the state dir."
            )
            report.note(
                "PRODUCTION DEFECT: json_store save/read id-sanitisation asymmetry "
                "(save_mission/save_approval raw, get_mission/get_approval via _safe_name). "
                "Latent today because ids are `mission-<hex>`. Covered by two xfail tests in "
                "tests/test_persistence.py."
            )
        else:
            report.ok("json_store save and read paths sanitise ids consistently")
    else:
        report.skip("could not locate JsonFileStore.save_mission / get_mission")

    tools_py = NEXUS_API / "services" / "tools.py"
    verify = _function_source(tools_py, "_verify_approval")
    for field in ("missionId", "agentId", "tool", "ApprovalStatus.granted"):
        report.check(
            field in verify, f"_verify_approval checks {field}"
        )

    execute = _function_source(tools_py, "execute_tool")
    if execute:
        deny_at = execute.find("PolicyOutcome.deny")
        approval_at = execute.find("PolicyOutcome.require_approval")
        report.check(
            0 <= deny_at < approval_at,
            "execute_tool evaluates DENY before any approval handling, so a token "
            "cannot launder a denied call",
        )

    mission_py = NEXUS_API / "services" / "mission.py"
    scan = _function_source(mission_py, "_scan_returned_documents", "MissionService")
    if scan and "if not path.exists():" in scan and "logger" not in scan:
        report.defect(
            "mission._scan_returned_documents skips a missing document silently (no log, no "
            "event), so a deleted synthetic fixture disables the prompt-injection guardrail "
            "without a single failing signal."
        )
        report.note(
            "PRODUCTION DEFECT: _scan_returned_documents silently skips absent documents, so "
            "the security guarantee can evaporate with no warning."
        )
    elif scan:
        report.ok("_scan_returned_documents reports a missing document")
    else:
        report.skip("could not locate MissionService._scan_returned_documents")

    # The two independently-computed project roots.
    storage_root = resolve_data_dir().parent
    adk_py = NEXUS_API / "services" / "adk_runtime.py"
    adk_root = None
    for parent in [adk_py, *adk_py.parents]:
        if (parent / "data").exists() and (parent / "agents").exists():
            adk_root = parent
            break
    if adk_root is not None and adk_root != storage_root:
        report.defect(
            f"storage resolves PROJECT_ROOT to {storage_root} but adk_runtime resolves it to "
            f"{adk_root}, so the dataset and the agent system prompts load from different trees."
        )
        report.note(
            f"PRODUCTION DEFECT: storage.PROJECT_ROOT ({storage_root}) != "
            f"adk_runtime.PROJECT_ROOT ({adk_root}). The two find_project_root() helpers use "
            "different rules, and storage's choice depends on files that are untracked in git, "
            "so a fresh clone resolves a different dataset than this working tree."
        )
    else:
        report.ok("storage and adk_runtime agree on the project root")


# ── main ────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verbose", "-v", action="store_true", help="print passing checks too")
    parser.add_argument(
        "--fail-on-defect",
        action="store_true",
        help="exit non-zero when a production defect is confirmed (default: report only)",
    )
    args = parser.parse_args()

    report = Report(verbose=args.verbose)
    print("NEXUS stdlib-only verification")
    print(f"repo root: {REPO_ROOT}")
    print(f"python:    {sys.version.split()[0]}")

    check_dependencies(report)
    check_pytest_config(report)
    check_no_duplicate_test_files(report)
    check_retired_identifiers(report)
    check_syntax(report)
    check_test_inventory(report)
    defaults = check_identity_defaults(report)
    data_dir = check_dataset(report, defaults)
    check_prompt_injection_fixture(report, data_dir)
    check_reported_defects(report)

    report.section("Summary")
    print(f"  checks passed        : {report.passed}")
    print(f"  checks failed        : {report.failed}")
    print(f"  checks skipped       : {report.skipped}")
    print(f"  production defects   : {len(report.defects)}")

    if report.defects:
        print("\n  PRODUCTION DEFECTS CONFIRMED (reported here, not fixed by the test suite):")
        for index, defect in enumerate(report.defects, start=1):
            print(f"    {index}. {defect}")

    if report.notes:
        print("\n  Notes:")
        for note in report.notes:
            print(f"    - {note}")

    print(
        "\n  NOT VERIFIED HERE (needs the real dependencies): policy evaluation, mission\n"
        "  orchestration and concurrency, approval park/resume, circuit breakers,\n"
        "  persistence round-trips, every FastAPI route, and all Gemini/ADK/Firestore\n"
        "  behaviour. Install with `pip install -e \"apps/api[dev]\"` and run `pytest`."
    )
    if report.failed:
        return 1
    if args.fail_on_defect and report.defects:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
