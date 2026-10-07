import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db
from app.core.rate_limit import reset_rate_limit_store


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    reset_rate_limit_store()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_register_and_login_flow(client: TestClient):
    # Register new user
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "sarah@example.com",
            "password": "StrongPassword123!",
            "full_name": "Sarah Connor",
            "workspace_name": "Resistance Hub",
        },
    )
    assert res.status_code == 201, res.text
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "sarah@example.com"
    token = data["access_token"]

    # Verify /me endpoint
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "sarah@example.com"

    # Login with valid credentials
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "sarah@example.com", "password": "StrongPassword123!"},
    )
    assert login_res.status_code == 200
    assert "access_token" in login_res.json()

    # Login with invalid password
    bad_login = client.post(
        "/api/v1/auth/login",
        json={"email": "sarah@example.com", "password": "WrongPassword!"},
    )
    assert bad_login.status_code == 401


def test_register_duplicate_email(client: TestClient):
    payload = {
        "email": "duplicate@example.com",
        "password": "password1234",
        "full_name": "First User",
    }
    res1 = client.post("/api/v1/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/v1/auth/register", json=payload)
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]


def test_protected_route_without_token(client: TestClient):
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401
