import logging
import time
import pytest
from fastapi.testclient import TestClient
from app.main import app


def test_health_endpoint():
    client = TestClient(app)
    start = time.time()
    response = client.get("/health")
    duration_ms = (time.time() - start) * 1000

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert duration_ms < 50, f"Health check took {duration_ms}ms, expected under 50ms"


def test_input_over_2000_chars_returns_422():
    client = TestClient(app)
    long_text = "x" * 2500

    # Test /api/bias with > 2000 char input
    res1 = client.post("/api/bias", json={"job_description": long_text})
    assert res1.status_code == 422

    # Test /api/compliance with > 2000 char input
    res2 = client.post("/api/compliance", json={"content": long_text})
    assert res2.status_code == 422


def test_rate_limiting_6th_request_returns_429():
    client = TestClient(app)
    payload = {"job_description": "We are looking for a senior developer."}
    headers = {"X-Forwarded-For": "10.0.0.99"}

    statuses = []
    for _ in range(5):
        r = client.post("/api/bias", json=payload, headers=headers)
        statuses.append(r.status_code)

    r6 = client.post("/api/bias", json=payload, headers=headers)

    assert statuses == [200, 200, 200, 200, 200]
    assert r6.status_code == 429


def test_privacy_no_request_body_in_logs(caplog):
    client = TestClient(app)
    caplog.set_level(logging.INFO)

    secret_input = "SECRET_UNTRACKED_TEXT_PAYLOAD_98765"
    payload = {"job_description": secret_input}
    headers = {"X-Forwarded-For": "10.0.0.50"}

    response = client.post("/api/bias", json=payload, headers=headers)
    assert response.status_code in [200, 429]

    log_content = caplog.text
    assert secret_input not in log_content
    assert "job_description" not in log_content
