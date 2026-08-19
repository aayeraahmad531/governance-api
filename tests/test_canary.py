import logging
from fastapi.testclient import TestClient
from app.main import app


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

    # (c) Unhandled 500 Error
    res_c = client.post(
        "/api/debug-crash",
        json={"job_description": canary},
        headers={"X-Forwarded-For": "10.1.1.3"}
    )
    assert res_c.status_code == 500
    assert canary not in res_c.text

    # Grep ALL captured logs for CANARY_STRING_XYZ
    log_output = caplog.text
    assert canary not in log_output, f"PRIVACY CANARY LEAK DETECTED!\nLog output:\n{log_output}"
