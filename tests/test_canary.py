import logging
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings


def test_privacy_canary_zero_leakage(caplog):
    client = TestClient(app, raise_server_exceptions=False)
    caplog.set_level(logging.DEBUG)

    canary = "CANARY_STRING_XYZ_SECRET_TOKEN_9999"

    # (a) Normal 200 OK
    res_a = client.post(
        "/api/bias",
        json={"job_description": f"Hiring engineer with {canary}"},
        headers={"X-Forwarded-For": "10.1.1.1"}
    )
    assert res_a.status_code == 200

    # (b) 422 Validation Error
    long_input = f"{canary} " + ("x" * 2500)
    res_b = client.post(
        "/api/bias",
        json={"job_description": long_input},
        headers={"X-Forwarded-For": "10.1.1.2"}
    )
    assert res_b.status_code == 422
    assert canary not in res_b.text

    # (c1) Production Security Check: When DEBUG=False, /api/debug-crash MUST return 404 Not Found
    settings.DEBUG = False
    res_c1 = client.post("/api/debug-crash", json={"job_description": canary})
    assert res_c1.status_code == 404, f"Security Breach! /api/debug-crash returned {res_c1.status_code} instead of 404 when DEBUG=False!"

    # (c2) Unhandled 500 Error Traceback Privacy Test (enabled with DEBUG=True)
    settings.DEBUG = True
    try:
        res_c2 = client.post(
            "/api/debug-crash",
            json={"job_description": canary},
            headers={"X-Forwarded-For": "10.1.1.3"}
        )
        assert res_c2.status_code == 500
        assert canary not in res_c2.text
    finally:
        settings.DEBUG = False

    # Grep ALL captured logs for CANARY_STRING_XYZ
    log_output = caplog.text
    assert canary not in log_output, f"PRIVACY CANARY LEAK DETECTED!\nLog output:\n{log_output}"
