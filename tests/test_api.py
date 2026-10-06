from pathlib import Path

from fastapi.testclient import TestClient

from app.main import build_app


def make_client(tmp_path: Path) -> TestClient:
    return TestClient(build_app(":memory:", tmp_path / "documents"))


def test_seeded_documents_are_downloadable_with_security_headers(tmp_path: Path):
    with make_client(tmp_path) as client:
        listed = client.get("/api/documents", headers={"X-Demo-Role": "viewer"})
        assert listed.status_code == 200
        assert len(listed.json()) == 3
        response = client.get(f"/api/documents/{listed.json()[0]['id']}/download", headers={"X-Demo-Role": "viewer"})
        assert response.status_code == 200
        assert response.content.startswith(b"%PDF")
        assert response.headers["x-content-type-options"] == "nosniff"


def test_soft_delete_and_restore_are_admin_only(tmp_path: Path):
    with make_client(tmp_path) as client:
        assert client.delete("/api/documents/1", headers={"X-Demo-Role": "viewer"}).status_code == 403
        assert client.delete("/api/documents/1", headers={"X-Demo-Role": "admin"}).status_code == 200
        deleted = client.get("/api/documents?status=deleted", headers={"X-Demo-Role": "admin"}).json()
        assert [item["id"] for item in deleted] == [1]
        assert client.post("/api/documents/1/restore", headers={"X-Demo-Role": "admin"}).status_code == 200
