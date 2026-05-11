import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from db.database import Base, get_db
import db.models  # noqa: F401 — registers ORM models against Base


TEST_DB_URL = "sqlite://"


@pytest.fixture(scope="module")
def test_db_override():
    # StaticPool ensures every connection shares the same in-memory database
    engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    return override_get_db


@pytest.fixture(scope="module")
def client(test_db_override):
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from api.library import router as library_router
    from api.cases import router as cases_router

    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    test_app.include_router(library_router, prefix="/api/v1/library")
    test_app.include_router(cases_router, prefix="/api/v1/cases")
    test_app.dependency_overrides[get_db] = test_db_override

    yield TestClient(test_app)
    test_app.dependency_overrides.clear()


# ── library ──

def test_list_spectra_empty(client):
    resp = client.get("/api/v1/library/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_spectrum(client):
    resp = client.post("/api/v1/library/", json={
        "material_name": "PP",
        "grade": "T30S",
        "supplier": "中石化",
        "created_by": "test",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["material_name"] == "PP"
    assert data["id"] == 1


def test_get_spectrum(client):
    resp = client.get("/api/v1/library/1")
    assert resp.status_code == 200
    assert resp.json()["material_name"] == "PP"


def test_update_spectrum(client):
    resp = client.put("/api/v1/library/1", json={"grade": "T30G"})
    assert resp.status_code == 200
    assert resp.json()["grade"] == "T30G"


def test_delete_spectrum(client):
    resp = client.delete("/api/v1/library/1")
    assert resp.status_code == 204
    resp2 = client.get("/api/v1/library/1")
    assert resp2.status_code == 404


# ── cases ──

def test_list_cases_empty(client):
    resp = client.get("/api/v1/cases/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_nonexistent_case(client):
    resp = client.get("/api/v1/cases/FA-2026-999")
    assert resp.status_code == 404
