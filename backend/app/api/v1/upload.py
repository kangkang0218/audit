from __future__ import annotations

import hashlib
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

router = APIRouter(tags=["chunk-upload"])

UPLOAD_ROOT = Path("/app/uploads")
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
CHUNK_MAX = 50 * 1024 * 1024
SESSION_TTL = 86400

sessions: dict[str, dict[str, Any]] = {}


class InitRequest(BaseModel):
    fileName: str
    fileSize: int
    chunkSize: int = CHUNK_MAX
    contentType: str = "application/octet-stream"
    checksum: str | None = None


def _cleanup_expired() -> None:
    now = time.time()
    expired = [k for k, v in sessions.items() if now - v["created_at"] > SESSION_TTL]
    for k in expired:
        _delete_session(k)


def _delete_session(upload_id: str) -> None:
    tmp_dir = UPLOAD_ROOT / upload_id
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir, ignore_errors=True)
    sessions.pop(upload_id, None)


def _session_dir(upload_id: str) -> Path:
    d = UPLOAD_ROOT / upload_id
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/upload/init")
def upload_init(body: InitRequest) -> dict[str, Any]:
    _cleanup_expired()
    upload_id = uuid.uuid4().hex
    chunk_count = (body.fileSize + body.chunkSize - 1) // body.chunkSize
    sessions[upload_id] = {
        "upload_id": upload_id,
        "file_name": body.fileName,
        "file_size": body.fileSize,
        "chunk_size": body.chunkSize,
        "chunk_count": chunk_count,
        "content_type": body.contentType,
        "checksum": body.checksum,
        "uploaded_chunks": set(),
        "status": "UPLOADING",
        "created_at": time.time(),
    }
    _session_dir(upload_id)
    return {"uploadId": upload_id, "chunkCount": chunk_count, "chunkSize": body.chunkSize}


@router.get("/upload/health")
def upload_health() -> dict[str, Any]:
    return {"status": "UP", "activeSessions": len(sessions)}


@router.get("/upload/{upload_id}")
def upload_status(upload_id: str) -> dict[str, Any]:
    s = sessions.get(upload_id)
    if not s:
        raise HTTPException(status_code=404, detail="UPLOAD_NOT_FOUND")
    return {
        "uploadId": s["upload_id"],
        "fileName": s["file_name"],
        "fileSize": s["file_size"],
        "chunkSize": s["chunk_size"],
        "chunkCount": s["chunk_count"],
        "uploadedChunks": sorted(s["uploaded_chunks"]),
        "status": s["status"],
        "createdAt": s["created_at"],
    }


@router.get("/upload/{upload_id}/chunks")
def uploaded_chunks(upload_id: str) -> dict[str, Any]:
    s = sessions.get(upload_id)
    if not s:
        raise HTTPException(status_code=404, detail="UPLOAD_NOT_FOUND")
    return {
        "uploadId": s["upload_id"],
        "uploadedChunks": sorted(s["uploaded_chunks"]),
        "uploadedCount": len(s["uploaded_chunks"]),
        "chunkCount": s["chunk_count"],
    }


@router.post("/upload/{upload_id}/chunks/{chunk_index}")
def upload_chunk(upload_id: str, chunk_index: int, chunk: UploadFile = File(...)) -> dict[str, Any]:
    s = sessions.get(upload_id)
    if not s:
        raise HTTPException(status_code=404, detail="UPLOAD_NOT_FOUND")
    if s["status"] != "UPLOADING":
        raise HTTPException(status_code=409, detail="INVALID_STATE")
    if not (0 <= chunk_index < s["chunk_count"]):
        raise HTTPException(status_code=400, detail="BAD_REQUEST")

    chunk_dir = _session_dir(upload_id)
    chunk_path = chunk_dir / f"{chunk_index}.part"
    content = chunk.file.read()
    if len(content) > CHUNK_MAX + 1024 * 1024:
        raise HTTPException(status_code=413, detail="CHUNK_TOO_LARGE")

    if chunk_path.exists():
        existing_hash = hashlib.md5(chunk_path.read_bytes()).hexdigest()
        new_hash = hashlib.md5(content).hexdigest()
        if existing_hash != new_hash:
            raise HTTPException(status_code=409, detail="UPLOAD_CONFLICT")
    else:
        chunk_path.write_bytes(content)

    s["uploaded_chunks"].add(chunk_index)
    return {
        "uploadId": s["upload_id"],
        "uploadedChunks": sorted(s["uploaded_chunks"]),
        "uploadedCount": len(s["uploaded_chunks"]),
        "chunkCount": s["chunk_count"],
    }


@router.post("/upload/{upload_id}/complete")
def complete_upload(upload_id: str) -> dict[str, Any]:
    s = sessions.get(upload_id)
    if not s:
        raise HTTPException(status_code=404, detail="UPLOAD_NOT_FOUND")
    if s["status"] != "UPLOADING":
        raise HTTPException(status_code=409, detail="INVALID_STATE")
    if len(s["uploaded_chunks"]) != s["chunk_count"]:
        raise HTTPException(status_code=400, detail="INCOMPLETE_UPLOAD")

    final_dir = UPLOAD_ROOT / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    final_path = final_dir / f"{upload_id}-{s['file_name']}"
    final_hash = hashlib.md5()

    with final_path.open("wb") as out:
        for i in range(s["chunk_count"]):
            chunk_path = _session_dir(upload_id) / f"{i}.part"
            data = chunk_path.read_bytes()
            out.write(data)
            final_hash.update(data)

    md5_hex = final_hash.hexdigest()
    if s["checksum"] and s["checksum"] != md5_hex:
        final_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"CHECKSUM_MISMATCH: expected {s['checksum']}, got {md5_hex}")

    s["status"] = "COMPLETED"
    return {
        "uploadId": s["upload_id"],
        "fileName": s["file_name"],
        "fileSize": s["file_size"],
        "filePath": str(final_path),
        "checksum": md5_hex,
    }


