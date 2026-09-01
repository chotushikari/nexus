import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1] / "apps" / "api"
sys.path.insert(0, str(API_ROOT))

from fastapi.testclient import TestClient
import pytest

from nexus_api.application import create_app
from nexus_api.services.storage import store


@pytest.fixture()
def client() -> TestClient:
    store.reset()
    return TestClient(create_app())

