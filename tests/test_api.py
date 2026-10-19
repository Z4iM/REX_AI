
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------
# Test 1: Health Check
# ---------------------------------------
def test_health_endpoint(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert isinstance(response.json(), dict)


# ---------------------------------------
# Test 2: OpenAPI Documentation
# ---------------------------------------
def test_openapi_endpoints(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200

    paths = response.json()["paths"]

    required_endpoints = [
        "/health",
        "/api/v1/chat",
        "/api/v1/qualification",
        "/api/v1/qualification/{session_id}/recommendation",
    ]

    for endpoint in required_endpoints:
        assert endpoint in paths, (
            f"Missing API endpoint: {endpoint}"
        )


# ---------------------------------------
# Test 3: Empty Chat Message
# ---------------------------------------
def test_empty_chat_message(client):
    response = client.post(
        "/api/v1/chat",
        json={"message": ""},
    )

    assert response.status_code == 422


# ---------------------------------------
# Test 4: Punctuation-only Message
# ---------------------------------------
def test_invalid_chat_message(client):
    response = client.post(
        "/api/v1/chat",
        json={"message": "!!!"},
    )

    assert response.status_code == 422


# ---------------------------------------
# Test 5: Unknown Recommendation Session
# ---------------------------------------
def test_unknown_recommendation_session(client):
    response = client.post(
        "/api/v1/qualification/"
        "nonexistent-session-id/recommendation"
    )

    assert response.status_code == 404


# ---------------------------------------
# Test 6: Unsupported Request Method
# ---------------------------------------
def test_chat_get_not_allowed(client):
    response = client.get("/api/v1/chat")

    assert response.status_code == 405
