import hashlib
import io
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .director import PROMPT_VERSION, GeminiProvider, ProviderError, vision_provider
from .schemas import OOREDOO, Audit, AuditRequest, PromptRequest, assemble_prompt
from .storage import Asset, AuditRecord, Base, PromptRevision, make_storage

MAX_BYTES = 15 * 1024 * 1024
MAX_PIXELS = 50_000_000
MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
COOKIE = "director_session"


def owner_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


@asynccontextmanager
async def lifespan(app):
    app.state.engine, app.state.objects = make_storage()
    Base.metadata.create_all(app.state.engine)
    try:
        yield
    finally:
        app.state.engine.dispose()


app = FastAPI(title="Visual Director AI", lifespan=lifespan)


def owned_asset(db, request, asset_id):
    token = request.cookies.get(COOKIE, "")
    asset = db.get(Asset, str(asset_id))
    if not token or not asset or not secrets.compare_digest(asset.owner, owner_hash(token)):
        raise HTTPException(404, "Image not found in this workspace.")
    return asset


@app.get("/config")
def config():
    provider = vision_provider()
    return {"vision_configured": bool(provider.key), "sample_brand": OOREDOO,
            "credential_name": "GEMINI_API_KEY" if isinstance(provider, GeminiProvider) else "VISION_API_KEY"}


@app.post("/assets", status_code=201)
def upload(request: Request, response: Response, file: UploadFile = File(...)):
    data = file.file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Choose an image up to 15 MiB.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            mime = MIME.get(image.format)
            if not mime or getattr(image, "n_frames", 1) != 1:
                raise HTTPException(415, "Choose a still JPG, PNG or WebP.")
            if image.width * image.height > MAX_PIXELS:
                raise HTTPException(413, "Choose an image up to 50 megapixels.")
            oriented = ImageOps.exif_transpose(image)
            width, height = oriented.size
    except Image.DecompressionBombError as exc:
        raise HTTPException(413, "Choose an image up to 50 megapixels.") from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise HTTPException(415, "The file is not a readable JPG, PNG or WebP.") from exc

    token = request.cookies.get(COOKIE) or secrets.token_urlsafe(32)
    asset_id = str(uuid4())
    filename = (file.filename or "image").replace("\\", "/").rsplit("/", 1)[-1][:255]
    objects = request.app.state.objects
    objects.put(asset_id, data, mime)
    try:
        with Session(request.app.state.engine) as db:
            db.add(Asset(id=asset_id, owner=owner_hash(token), filename=filename,
                         mime=mime, width=width, height=height, size=len(data)))
            db.commit()
    except Exception:
        objects.delete(asset_id)
        raise
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax",
                        secure=os.getenv("COOKIE_SECURE") == "1", max_age=30 * 24 * 3600)
    return {"id": asset_id, "filename": filename, "mime": mime, "width": width, "height": height, "size": len(data)}


@app.get("/assets/{asset_id}/image")
def image(request: Request, asset_id: UUID):
    with Session(request.app.state.engine) as db:
        asset = owned_asset(db, request, asset_id)
        data = request.app.state.objects.get(asset.id)
        return Response(data, media_type=asset.mime, headers={"Cache-Control": "private, no-store",
                         "X-Content-Type-Options": "nosniff"})


@app.post("/audits", status_code=201)
def audit(request: Request, body: AuditRequest):
    with Session(request.app.state.engine) as db:
        asset = owned_asset(db, request, body.asset_id)
        provider = vision_provider()
        if not provider.key:
            raise HTTPException(503, f"Set {config()['credential_name']} on the server to enable creative analysis.")
        data = request.app.state.objects.get(asset.id)
    try:
        result = provider.analyze(data, body)
    except ProviderError as exc:
        raise HTTPException(502, str(exc)) from exc
    audit_id = str(uuid4())
    with Session(request.app.state.engine) as db:
        db.add(AuditRecord(id=audit_id, asset_id=str(body.asset_id),
                           request=body.model_dump(mode="json"), result=result.model_dump(),
                           provider_model=provider.model, prompt_version=PROMPT_VERSION, created_at=datetime.now(timezone.utc).isoformat()))
        db.commit()
    return {"id": audit_id, "result": result}


@app.post("/audits/{audit_id}/prompts", status_code=201)
def prompt(request: Request, audit_id: UUID, body: PromptRequest):
    with Session(request.app.state.engine) as db:
        record = db.get(AuditRecord, str(audit_id))
        if not record:
            raise HTTPException(404, "Audit not found in this workspace.")
        owned_asset(db, request, record.asset_id)
        if body.text is not None and not body.text.strip():
            raise HTTPException(422, "Enter a prompt before saving.")
        text = body.text if body.text is not None else assemble_prompt(
            Audit.model_validate(record.result), AuditRequest.model_validate(record.request), body.treatment)
        revision = PromptRevision(id=str(uuid4()), audit_id=record.id, treatment=body.treatment,
                                  text=text, created_at=datetime.now(timezone.utc).isoformat())
        db.add(revision)
        db.commit()
        return {"id": revision.id, "treatment": revision.treatment, "text": revision.text,
                "created_at": revision.created_at}


@app.get("/assets/{asset_id}/audit")
def latest_audit(request: Request, asset_id: UUID):
    with Session(request.app.state.engine) as db:
        asset = owned_asset(db, request, asset_id)
        record = db.scalar(select(AuditRecord).where(AuditRecord.asset_id == asset.id)
                           .order_by(AuditRecord.created_at.desc(), AuditRecord.id.desc()).limit(1))
        if not record:
            return {"asset": {"id": asset.id, "filename": asset.filename, "mime": asset.mime,
                              "width": asset.width, "height": asset.height, "size": asset.size},
                    "audit": None}
        revision = db.scalar(select(PromptRevision).where(PromptRevision.audit_id == record.id)
                             .order_by(PromptRevision.created_at.desc(), PromptRevision.id.desc()).limit(1))
        return {"asset": {"id": asset.id, "filename": asset.filename, "mime": asset.mime,
                          "width": asset.width, "height": asset.height, "size": asset.size},
                "audit": {"id": record.id, "result": record.result}, "request": record.request,
                "prompt": {"text": revision.text, "treatment": revision.treatment} if revision else None}
