from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from .security import safe_document_path, validate_pdf_name
from .store import add_document, connect


BASE_DIR = Path(__file__).resolve().parent


def demo_role(x_demo_role: str = Header(default="viewer")) -> str:
    role = x_demo_role.lower()
    if role not in {"viewer", "editor", "admin"}:
        raise HTTPException(403, "Unknown demo role")
    return role


def require_admin(role: str = Depends(demo_role)) -> str:
    if role != "admin":
        raise HTTPException(403, "Admin role required")
    return role


def create_pdf(path: Path, title: str, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.setTitle(title)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(72, 770, title)
    pdf.setFont("Helvetica", 10)
    text = pdf.beginText(72, 735)
    for line in body.splitlines():
        text.textLine(line)
    pdf.drawText(text)
    pdf.setFont("Helvetica-Oblique", 8)
    pdf.drawString(72, 55, "Synthetic document generated for a public portfolio demo.")
    pdf.save()


def build_app(database_path: str | None = None, storage_root: str | Path | None = None) -> FastAPI:
    data_root = Path(storage_root or os.getenv("DOCUMENT_STORAGE", BASE_DIR.parent / ".data" / "documents"))
    active_root = data_root / "active"
    trash_root = data_root / "trash"
    active_root.mkdir(parents=True, exist_ok=True)
    trash_root.mkdir(parents=True, exist_ok=True)
    db_path = database_path or os.getenv("DOCUMENT_DATABASE", str(data_root.parent / "documents.db"))
    connection = connect(db_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        connection.close()

    app = FastAPI(title="Secure Document Library Demo", version="1.0.0", lifespan=lifespan)
    app.state.db = connection
    app.state.active_root = active_root
    app.state.trash_root = trash_root
    app.state.rate_events = defaultdict(deque)

    fixtures = (
        ("operations-handbook.pdf", "Operations Handbook", "Operations", "Fictional operating procedures\nVersion 2.4\nReview cycle: quarterly"),
        ("security-baseline.pdf", "Security Baseline", "Security", "Synthetic access-control standard\nNo production configuration is included."),
        ("vendor-onboarding.pdf", "Vendor Onboarding", "Procurement", "Demo checklist for a fictional supplier workflow."),
    )
    if connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == 0:
        for filename, title, category, body in fixtures:
            target = active_root / filename
            create_pdf(target, title, body)
            add_document(connection, filename, title, category, target.stat().st_size, "system")

    @app.middleware("http")
    async def hardening(request: Request, call_next):
        now = time.monotonic()
        bucket = app.state.rate_events[request.client.host if request.client else "local"]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= 120:
            raise HTTPException(429, "Rate limit exceeded")
        bucket.append(now)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'"
        return response

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "data": "synthetic"}

    @app.get("/api/documents")
    def list_documents(status: str = "active", _: str = Depends(demo_role)) -> list[dict]:
        if status not in {"active", "deleted"}:
            raise HTTPException(400, "Invalid document status")
        rows = connection.execute(
            "SELECT * FROM documents WHERE status = ? ORDER BY created_at DESC, id DESC", (status,)
        ).fetchall()
        return [dict(row) for row in rows]

    @app.get("/api/documents/{document_id}/download")
    def download(document_id: int, _: str = Depends(demo_role)) -> FileResponse:
        document = connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if document is None or document["status"] != "active":
            raise HTTPException(404, "Document not found")
        try:
            path = safe_document_path(active_root, document["filename"])
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        if not path.exists():
            raise HTTPException(404, "Stored file missing")
        return FileResponse(path, media_type="application/pdf", filename=document["filename"])

    @app.post("/api/documents", status_code=201)
    async def upload(
        title: str = Form(min_length=2, max_length=120),
        category: str = Form(min_length=2, max_length=60),
        document: UploadFile = File(),
        role: str = Depends(require_admin),
    ) -> dict:
        try:
            filename = validate_pdf_name(document.filename or "")
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        content = await document.read(2_000_001)
        if len(content) > 2_000_000:
            raise HTTPException(413, "Demo upload limit is 2 MB")
        if not content.startswith(b"%PDF"):
            raise HTTPException(400, "File content is not a PDF")
        target = safe_document_path(active_root, filename)
        if target.exists():
            raise HTTPException(409, "Filename already exists")
        target.write_bytes(content)
        try:
            document_id = add_document(connection, filename, title, category, len(content), role)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return dict(connection.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone())

    @app.delete("/api/documents/{document_id}")
    def delete(document_id: int, role: str = Depends(require_admin)) -> dict[str, str]:
        document = connection.execute("SELECT * FROM documents WHERE id = ? AND status = 'active'", (document_id,)).fetchone()
        if document is None:
            raise HTTPException(404, "Document not found")
        source = safe_document_path(active_root, document["filename"])
        destination = safe_document_path(trash_root, document["filename"])
        source.replace(destination)
        connection.execute("UPDATE documents SET status='deleted', deleted_at=CURRENT_TIMESTAMP WHERE id=?", (document_id,))
        connection.execute(
            "INSERT INTO audit_log (actor_role, action, document_id, details) VALUES (?, 'soft_deleted', ?, ?)",
            (role, document_id, document["filename"]),
        )
        connection.commit()
        return {"status": "deleted"}

    @app.post("/api/documents/{document_id}/restore")
    def restore(document_id: int, role: str = Depends(require_admin)) -> dict[str, str]:
        document = connection.execute("SELECT * FROM documents WHERE id = ? AND status = 'deleted'", (document_id,)).fetchone()
        if document is None:
            raise HTTPException(404, "Deleted document not found")
        source = safe_document_path(trash_root, document["filename"])
        destination = safe_document_path(active_root, document["filename"])
        source.replace(destination)
        connection.execute("UPDATE documents SET status='active', deleted_at=NULL WHERE id=?", (document_id,))
        connection.execute(
            "INSERT INTO audit_log (actor_role, action, document_id, details) VALUES (?, 'restored', ?, ?)",
            (role, document_id, document["filename"]),
        )
        connection.commit()
        return {"status": "active"}

    @app.get("/api/audit")
    def audit(_: str = Depends(require_admin)) -> list[dict]:
        return [dict(row) for row in connection.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 100").fetchall()]

    app.mount("/assets", StaticFiles(directory=BASE_DIR / "static"), name="assets")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(BASE_DIR / "static" / "index.html")

    return app


app = build_app()
