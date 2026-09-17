import base64
import re
import hashlib
import io
import os
from typing import Optional

from fastapi import (APIRouter, Depends, File, Form, HTTPException, Request,
                     UploadFile, status)
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from ..authz import agent_scope, assert_in_scope, attachment_target_engagement
from ..config import settings
from ..constants import AttachmentTarget
from ..db import get_session
from ..deps import Principal, current_reader, current_writer
from ..models import Attachment

router = APIRouter(prefix="/attachments", tags=["attachments"])
_VALID = {t.value for t in AttachmentTarget}


def _sniff_mime(content: bytes, fallback: str) -> str:
    """Detect common types from magic bytes so a wrong/default mime is corrected."""
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if content[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    if content[:5] == b"%PDF-":
        return "application/pdf"
    return fallback or "application/octet-stream"


def _decode_b64(data: str) -> bytes:
    """Tolerant base64 decode: strips a data: URI prefix and any whitespace,
    fixes padding. Raises ValueError on genuinely invalid data."""
    raw = (data or "").strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    raw = "".join(raw.split())  # drop embedded newlines/spaces
    if not re.fullmatch(r"[A-Za-z0-9+/=]*", raw) or raw == "":
        raise ValueError("not valid base64")
    raw = raw.rstrip("=")
    raw += "=" * (-len(raw) % 4)  # fix missing/broken padding
    return base64.b64decode(raw)


def _blob_path(sha: str) -> str:
    return os.path.join(settings.blob_dir, sha[:2], sha[2:4], sha)


def _thumb_path(sha: str) -> str:
    return os.path.join(settings.blob_dir, "thumbs", f"{sha}.jpg")


def _store(content: bytes, mime: str) -> tuple[str, Optional[str]]:
    sha = hashlib.sha256(content).hexdigest()
    path = _blob_path(sha)
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(content)
    thumb = None
    if mime.startswith("image/"):
        try:
            from PIL import Image, ImageFile
            ImageFile.LOAD_TRUNCATED_IMAGES = True  # tolerate strict/slightly-off PNGs
            im = Image.open(io.BytesIO(content))
            im.load()
            im.thumbnail((480, 480))
            tp = _thumb_path(sha)
            os.makedirs(os.path.dirname(tp), exist_ok=True)
            im.convert("RGB").save(tp, "JPEG", quality=82)
            thumb = tp
        except Exception:
            thumb = None
    return sha, thumb


def _persist(session: Session, *, target_type: str, target_id: int, filename: str,
             mime: str, content: bytes, caption, source, actor) -> Attachment:
    if target_type not in _VALID:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"target_type must be one of {sorted(_VALID)}")
    cap = settings.max_upload_mb * 1024 * 1024
    if len(content) > cap:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            f"file exceeds {settings.max_upload_mb} MB")
    mime = _sniff_mime(content, mime)  # trust the bytes, not the caller-supplied mime
    sha, thumb = _store(content, mime)
    att = Attachment(target_type=target_type, target_id=target_id, filename=filename,
                     mime=mime, sha256=sha, size=len(content), caption=caption,
                     source=source or actor, thumb_path=thumb, author=actor)
    session.add(att); session.commit(); session.refresh(att)
    return att


@router.get("")
def list_attachments(request: Request, session: Session = Depends(get_session),
                     p: Principal = Depends(current_reader)):
    stmt = select(Attachment)
    tt = request.query_params.get("target_type")
    ti = request.query_params.get("target_id")
    if tt and ti and agent_scope(p) is not None:
        assert_in_scope(p, attachment_target_engagement(session, tt, int(ti)))
    if tt:
        stmt = stmt.where(Attachment.target_type == tt)
    if ti:
        stmt = stmt.where(Attachment.target_id == int(ti))
    rows = session.exec(stmt.order_by(Attachment.id.desc())).all()
    scope = agent_scope(p)
    if scope is not None:
        rows = [a for a in rows if attachment_target_engagement(session, a.target_type, a.target_id) == scope]
    return rows


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_attachment(target_type: str = Form(...), target_id: int = Form(...),
                            caption: Optional[str] = Form(None),
                            source: Optional[str] = Form(None),
                            file: UploadFile = File(...),
                            session: Session = Depends(get_session),
                            p: Principal = Depends(current_writer)):
    assert_in_scope(p, attachment_target_engagement(session, target_type, target_id))
    cap = settings.max_upload_mb * 1024 * 1024
    chunks, total = [], 0
    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > cap:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                f"file exceeds {settings.max_upload_mb} MB")
        chunks.append(chunk)
    content = b"".join(chunks)
    return _persist(session, target_type=target_type, target_id=target_id,
                    filename=file.filename or "upload", mime=file.content_type or "application/octet-stream",
                    content=content, caption=caption, source=source, actor=p.actor)


class Base64Upload(BaseModel):
    target_type: str
    target_id: int
    filename: str
    mime: str = "image/png"
    data_b64: str
    caption: Optional[str] = None
    source: Optional[str] = None


@router.post("/base64", status_code=status.HTTP_201_CREATED)
def upload_base64(body: Base64Upload, session: Session = Depends(get_session),
                  p: Principal = Depends(current_writer)):
    """Convenient path for agents (Claude Code) to attach a screenshot as base64."""
    try:
        content = _decode_b64(body.data_b64)
    except Exception:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid base64 data")
    if not content:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty file after base64 decode")
    assert_in_scope(p, attachment_target_engagement(session, body.target_type, body.target_id))
    return _persist(session, target_type=body.target_type, target_id=body.target_id,
                    filename=body.filename, mime=body.mime, content=content,
                    caption=body.caption, source=body.source, actor=p.actor)


class AttachmentUpdate(BaseModel):
    target_type: Optional[str] = None  # move to a different owner
    target_id: Optional[int] = None
    caption: Optional[str] = None


@router.patch("/{att_id}")
def update_attachment(att_id: int, body: AttachmentUpdate,
                      session: Session = Depends(get_session),
                      p: Principal = Depends(current_writer)):
    """Edit an attachment's caption and/or MOVE it to a different owner
    (e.g. re-target a screenshot from a finding to a service)."""
    att = session.get(Attachment, att_id)
    if not att:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attachment not found")
    # must be in scope for the CURRENT owner...
    assert_in_scope(p, attachment_target_engagement(session, att.target_type, att.target_id))
    data = body.model_dump(exclude_unset=True)
    if "target_type" in data or "target_id" in data:
        new_type = data.get("target_type", att.target_type)
        new_id = data.get("target_id", att.target_id)
        if new_type not in _VALID:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"target_type must be one of {sorted(_VALID)}")
        # ...and for the NEW owner
        assert_in_scope(p, attachment_target_engagement(session, new_type, new_id))
        att.target_type = new_type
        att.target_id = new_id
    if "caption" in data:
        att.caption = data["caption"]
    session.add(att); session.commit(); session.refresh(att)
    return att


@router.get("/{att_id}/download")
def download(att_id: int, session: Session = Depends(get_session),
             p: Principal = Depends(current_reader)):
    att = session.get(Attachment, att_id)
    if not att:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attachment not found")
    assert_in_scope(p, attachment_target_engagement(session, att.target_type, att.target_id))
    path = _blob_path(att.sha256)
    if not os.path.exists(path):
        raise HTTPException(status.HTTP_410_GONE, "blob missing on disk")
    return FileResponse(path, media_type=att.mime, filename=att.filename,
                        headers={"X-Content-Type-Options": "nosniff"})


@router.get("/{att_id}/thumb")
def thumb(att_id: int, session: Session = Depends(get_session),
          p: Principal = Depends(current_reader)):
    att = session.get(Attachment, att_id)
    if not att or not att.thumb_path or not os.path.exists(att.thumb_path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "thumbnail not available")
    assert_in_scope(p, attachment_target_engagement(session, att.target_type, att.target_id))
    return FileResponse(att.thumb_path, media_type="image/jpeg",
                        headers={"X-Content-Type-Options": "nosniff"})


@router.delete("/{att_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(att_id: int, session: Session = Depends(get_session),
                      p: Principal = Depends(current_writer)):
    att = session.get(Attachment, att_id)
    if not att:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attachment not found")
    assert_in_scope(p, attachment_target_engagement(session, att.target_type, att.target_id))
    sha = att.sha256
    session.delete(att); session.commit()
    # content-addressed dedupe: only remove the blob if nothing else references it
    others = session.exec(select(Attachment).where(Attachment.sha256 == sha)).first()
    if not others:
        for path in (_blob_path(sha), _thumb_path(sha)):
            try:
                os.remove(path)
            except OSError:
                pass
