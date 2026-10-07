import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import get_db
from app.core.security import create_access_token
from app.core.rate_limit import reset_rate_limit_store
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMembership


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


def test_tenant_isolation_workspaces(client: TestClient, db_session: Session):
    # Setup Tenant 1: Org Alpha
    user_alpha = User(email="alpha@org.com", hashed_password="pw", full_name="Alpha Lead")
    ws_alpha = Workspace(name="Alpha Org", slug="alpha-org")
    db_session.add_all([user_alpha, ws_alpha])
    db_session.flush()

    m_alpha = WorkspaceMembership(user_id=user_alpha.id, workspace_id=ws_alpha.id, role="owner")
    db_session.add(m_alpha)

    # Setup Tenant 2: Org Beta
    user_beta = User(email="beta@org.com", hashed_password="pw", full_name="Beta Lead")
    ws_beta = Workspace(name="Beta Org", slug="beta-org")
    db_session.add_all([user_beta, ws_beta])
    db_session.flush()

    m_beta = WorkspaceMembership(user_id=user_beta.id, workspace_id=ws_beta.id, role="owner")
    db_session.add(m_beta)
    db_session.commit()

    token_alpha = create_access_token(user_alpha.id)
    token_beta = create_access_token(user_beta.id)

    # User Alpha requests their own workspaces
    res_alpha = client.get(
        "/api/v1/workspaces",
        headers={"Authorization": f"Bearer {token_alpha}"},
    )
    assert res_alpha.status_code == 200
    workspaces = res_alpha.json()
    assert len(workspaces) == 1
    assert workspaces[0]["id"] == ws_alpha.id
    assert workspaces[0]["name"] == "Alpha Org"

    # User Beta adds member to Beta
    user_beta_member = User(email="dev@beta.com", hashed_password="pw", full_name="Beta Dev")
    db_session.add(user_beta_member)
    db_session.commit()

    add_res = client.post(
        "/api/v1/workspaces/members",
        headers={
            "Authorization": f"Bearer {token_beta}",
            "X-Workspace-ID": ws_beta.id,
        },
        json={"user_email": "dev@beta.com", "role": "member"},
    )
    assert add_res.status_code == 201

    # User Alpha tries to access Workspace Beta directly via header -> Must be 403 Forbidden!
    forbidden_res = client.post(
        "/api/v1/workspaces/members",
        headers={
            "Authorization": f"Bearer {token_alpha}",
            "X-Workspace-ID": ws_beta.id,
        },
        json={"user_email": "intruder@fake.com", "role": "member"},
    )
    assert forbidden_res.status_code == 403
    assert "forbidden" in forbidden_res.json()["detail"].lower()
