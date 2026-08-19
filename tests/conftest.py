import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.guards import limiter


@pytest.fixture(autouse=True)
def reset_limiter_storage():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def client():
    return TestClient(app)
