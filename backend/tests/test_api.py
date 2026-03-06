import json
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.database import Base, engine
from backend.app.main import app
from backend.app import models  # noqa: F401
from backend.app.services.ai import AIInterpreterService
from backend.app.services.execution import ExecutionEngineService

client = TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_request_flow(monkeypatch):
    def fake_interpret(request_text):
        return AIInterpreterService._fallback_instruction(request_text)

    def fake_execute(payload):
        from backend.app.schemas import WorkflowExecutionResult

        return WorkflowExecutionResult(status="success", output={"result": "ok", "payload": payload})

    monkeypatch.setattr(AIInterpreterService, "interpret_request", staticmethod(fake_interpret))
    monkeypatch.setattr(ExecutionEngineService, "execute", staticmethod(fake_execute))

    response = client.post(
        "/api/requests",
        json={"user_id": "qa@example.com", "request_text": "Fetch data and notify me"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["execution_status"] == "success"
    parsed_output = json.loads(body["execution_output"])
    assert parsed_output["result"] == "ok"


def test_api_key_required_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "api_access_key", "secret123")
    response = client.post(
        "/api/requests",
        json={"user_id": "qa@example.com", "request_text": "Fetch data and notify me"},
    )
    assert response.status_code == 401

    monkeypatch.setattr(settings, "api_access_key", "")


def test_idempotency_key_prevents_duplicate_execution(monkeypatch):
    calls = {"count": 0}

    def fake_interpret(request_text):
        return AIInterpreterService._fallback_instruction(request_text)

    def fake_execute(payload):
        from backend.app.schemas import WorkflowExecutionResult

        calls["count"] += 1
        return WorkflowExecutionResult(status="success", output={"result": "ok", "payload": payload})

    monkeypatch.setattr(AIInterpreterService, "interpret_request", staticmethod(fake_interpret))
    monkeypatch.setattr(ExecutionEngineService, "execute", staticmethod(fake_execute))

    headers = {"X-Idempotency-Key": f"idem-{uuid.uuid4()}"}
    response_1 = client.post(
        "/api/requests",
        headers=headers,
        json={"user_id": "qa@example.com", "request_text": "Fetch data and notify me"},
    )
    response_2 = client.post(
        "/api/requests",
        headers=headers,
        json={"user_id": "qa@example.com", "request_text": "Fetch data and notify me"},
    )

    assert response_1.status_code == 200
    assert response_2.status_code == 200
    assert response_1.json()["id"] == response_2.json()["id"]
    assert calls["count"] == 1
