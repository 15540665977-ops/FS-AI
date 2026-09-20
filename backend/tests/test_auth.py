import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import create_initial_admin
from core.security import hash_password
from db.database import Base, get_db
from db.models import User


@pytest.fixture
def auth_client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    from main import app

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, session_factory
    app.dependency_overrides.clear()


def test_unauthenticated_business_api_is_rejected(auth_client):
    client, _ = auth_client
    response = client.get("/api/v1/cases/")
    assert response.status_code == 401


def test_login_logout_and_admin_user_management(auth_client):
    client, session_factory = auth_client
    db = session_factory()
    db.add(User(username="admin", password_hash=hash_password("very-secure-admin-password"), is_admin=True))
    db.commit()
    db.close()

    response = client.post("/api/v1/auth/login", json={"username": "admin", "password": "very-secure-admin-password"})
    assert response.status_code == 200
    assert response.json()["is_admin"] is True

    created = client.post("/api/v1/auth/users", json={
        "username": "analyst",
        "password": "very-secure-analyst-password",
        "is_admin": False,
    })
    assert created.status_code == 201
    analyst_id = created.json()["id"]

    response = client.put(f"/api/v1/auth/users/{analyst_id}/active?is_active=false")
    assert response.status_code == 200
    assert response.json()["is_active"] is False

    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_bootstrap_admin_is_created_once(auth_client, monkeypatch):
    _, session_factory = auth_client
    monkeypatch.setenv("INITIAL_ADMIN_USERNAME", "bootstrap-admin")
    monkeypatch.setenv("INITIAL_ADMIN_PASSWORD", "very-secure-bootstrap-password")
    db = session_factory()
    create_initial_admin(db)
    assert db.query(User).count() == 1
    assert db.query(User).first().is_admin is True
    create_initial_admin(db)
    assert db.query(User).count() == 1
    db.close()
