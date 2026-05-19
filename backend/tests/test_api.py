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


# ── chat SSE ──

@pytest.fixture(scope="module")
def chat_client(test_db_override):
    """独立客户端，包含 chat 路由"""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from api.chat import router as chat_router

    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    test_app.include_router(chat_router, prefix="/api/v1/chat")
    test_app.dependency_overrides[get_db] = test_db_override
    yield TestClient(test_app)
    test_app.dependency_overrides.clear()


def test_stream_emits_spectra_data_event(chat_client, tmp_path):
    """流结束后应发出 spectra_data SSE 事件"""
    from PIL import Image
    from unittest.mock import AsyncMock, MagicMock
    img_path = tmp_path / "ir.png"
    Image.new("RGB", (100, 80), "white").save(img_path)

    fake_text_chunks = ["PP", " material"]
    fake_spectra = {
        "suggested_material": "PP",
        "observed_peaks": [{"wavenumber": 2920, "assignment": "CH2", "intensity": "强"}],
    }

    async def fake_stream(*a, **kw):
        for c in fake_text_chunks:
            yield c

    with patch("api.chat.get_orchestrator") as mock_get_orch:
        mock_orch = MagicMock()
        mock_orch.analyze_stream = fake_stream
        mock_orch.extract_peaks_structured = AsyncMock(return_value=fake_spectra)
        mock_get_orch.return_value = mock_orch

        with open(img_path, "rb") as f:
            resp = chat_client.post(
                "/api/v1/chat/stream",
                files={"files": ("ir.png", f, "image/png")},
                data={"analysis_type": "general"},
            )

    assert resp.status_code == 200
    body = resp.text
    spectra_lines = [
        l for l in body.splitlines()
        if l.startswith("data:") and '"spectra_data"' in l
    ]
    assert len(spectra_lines) == 1, f"期望 1 条 spectra_data 事件，实际：{spectra_lines}"
    import json
    payload = json.loads(spectra_lines[0][len("data: "):])
    assert payload["type"] == "spectra_data"
    assert payload["suggested_material"] == "PP"
    assert payload["observed_peaks"][0]["wavenumber"] == 2920
