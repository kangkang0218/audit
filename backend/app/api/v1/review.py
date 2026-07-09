from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from urllib.parse import quote

import fitz
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app.api.v1.upload import sessions, UPLOAD_ROOT
from app.core.config import Settings, get_settings
from app.services.async_runner import start_review, get_run, get_result_path, cleanup_run
from app.services.single_file_review import run_review_stream

router = APIRouter(tags=["single-file-review"])

SERVER_FILES_DIR = Path("/app/zzsj619")
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
UPLOAD_CHUNK_BYTES = 1024 * 1024


class LocalReviewRequest(BaseModel):
    filename: str
    mode: str = "bid_review_three_items"


class UploadReviewRequest(BaseModel):
    uploadId: str
    mode: str = "bid_review_three_items"


async def _save_uploaded_pdf(upload: UploadFile, target: Path, *, max_bytes: int) -> None:
    filename = Path(upload.filename or "").name
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="仅支持 PDF 文件。")
    server_file = _find_server_file(filename)
    if server_file is not None:
        shutil.copy2(server_file, target)
        return
    total = 0
    first_chunk = True
    with target.open("wb") as stream:
        while chunk := await upload.read(UPLOAD_CHUNK_BYTES):
            if first_chunk:
                first_chunk = False
                if not chunk.startswith(b"%PDF-"):
                    raise HTTPException(status_code=400, detail="文件内容不是有效的 PDF。")
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(status_code=413, detail="PDF 文件超过系统允许的大小。")
            stream.write(chunk)
    if total == 0:
        raise HTTPException(status_code=400, detail="上传的 PDF 文件为空。")


def _find_server_file(filename: str) -> Path | None:
    if not SERVER_FILES_DIR.is_dir():
        return None
    candidate = SERVER_FILES_DIR / Path(filename).name
    return candidate if candidate.is_file() else None


def _server_file_path(filename: str) -> Path | None:
    return _find_server_file(filename)


@router.post("/pdf-info")
async def pdf_info(pdf: UploadFile = File(...)) -> dict[str, int]:
    settings = get_settings()
    try:
        with tempfile.TemporaryDirectory(prefix="bid-review-info-") as temp_dir:
            input_path = Path(temp_dir) / "input.pdf"
            await _save_uploaded_pdf(pdf, input_path, max_bytes=settings.max_upload_bytes)
            try:
                with fitz.open(input_path) as doc:
                    page_count = len(doc)
            except Exception:
                raise HTTPException(status_code=400, detail="PDF 无法解析或已损坏。")
            return {"pageCount": page_count}
    finally:
        await pdf.close()


@router.post("/bid-review")
async def bid_review(
    request: Request,
    pdf: UploadFile = File(...),
    mode: str = Form(default="bid_review_three_items"),
) -> Response:
    if mode != "bid_review_three_items":
        raise HTTPException(status_code=422, detail="不支持的审查模式。")
    settings = get_settings()
    temp_dir = tempfile.TemporaryDirectory(prefix="bid-review-web-")
    try:
        working_dir = Path(temp_dir.name)
        input_path = working_dir / "input.pdf"
        output_dir = working_dir / "output"
        await _save_uploaded_pdf(pdf, input_path, max_bytes=settings.max_upload_bytes)

        use_sse = request.headers.get("X-Progress", "").lower() == "sse"
        if use_sse:
            async def sse_stream():
                async for event in run_review_stream(input_path, output_dir, settings):
                    import json as _json
                    data = _json.loads(event)
                    if data.get("stage") == "done":
                        rp = Path(data["result_path"])
                        import base64
                        b64 = base64.b64encode(rp.read_bytes()).decode()
                        yield f"data: {_json.dumps({**data, 'xlsx_b64': b64})}\n\n"
                        temp_dir.cleanup()
                        return
                    yield f"data: {event}\n\n"
            return StreamingResponse(sse_stream(), media_type="text/event-stream")

        async for event in run_review_stream(input_path, output_dir, settings):
            import json as _json
            data = _json.loads(event)
            if data.get("stage") == "done":
                result_path = Path(data["result_path"])
                content = result_path.read_bytes()
                encoded_name = quote(result_path.name)
                return Response(
                    content=content, media_type=XLSX_MEDIA_TYPE,
                    headers={
                        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
                        "X-Review-Mode": "local-only",
                    },
                )
        raise HTTPException(status_code=500, detail="审查未完成。")
    finally:
        await pdf.close()
        temp_dir.cleanup()


@router.get("/local-files")
async def list_local_files() -> list[dict[str, object]]:
    if not SERVER_FILES_DIR.is_dir():
        return []
    files: list[dict[str, object]] = []
    for path in sorted(SERVER_FILES_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() != ".pdf":
            continue
        try:
            with fitz.open(path) as doc:
                pc = len(doc)
        except Exception:
            pc = None
        files.append({"filename": path.name, "size": path.stat().st_size, "pageCount": pc})
    return files


@router.post("/local-review")
async def local_review(body: LocalReviewRequest) -> Response:
    if body.mode != "bid_review_three_items":
        raise HTTPException(status_code=422, detail="不支持的审查模式。")
    input_path = _server_file_path(body.filename)
    if input_path is None:
        raise HTTPException(status_code=404, detail=f"文件未找到：{body.filename}")
    settings = get_settings()
    temp_dir = tempfile.TemporaryDirectory(prefix="bid-review-local-")
    working_dir = Path(temp_dir.name)
    output_dir = working_dir / "output"
    try:
        async for event in run_review_stream(input_path, output_dir, settings):
            import json as _json
            data = _json.loads(event)
            if data.get("stage") == "done":
                result_path = Path(data["result_path"])
                content = result_path.read_bytes()
                encoded_name = quote(result_path.name)
                return Response(
                    content=content, media_type=XLSX_MEDIA_TYPE,
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}", "X-Review-Mode": "server-local"},
                )
    finally:
        temp_dir.cleanup()
    raise HTTPException(status_code=500, detail="审查未完成。")


@router.post("/local-review-stream")
async def local_review_stream(body: LocalReviewRequest) -> StreamingResponse:
    if body.mode != "bid_review_three_items":
        raise HTTPException(status_code=422, detail="不支持的审查模式。")
    input_path = _server_file_path(body.filename)
    if input_path is None:
        raise HTTPException(status_code=404, detail=f"文件未找到：{body.filename}")
    settings = get_settings()
    temp_dir = tempfile.TemporaryDirectory(prefix="bid-review-ss-")
    working_dir = Path(temp_dir.name)
    output_dir = working_dir / "output"

    async def event_stream():
        async for event in run_review_stream(input_path, output_dir, settings):
            yield f"data: {event}\n\n"
        temp_dir.cleanup()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/upload-review/start")
def upload_review_start(body: UploadReviewRequest) -> dict[str, str]:
    if body.mode != "bid_review_three_items":
        raise HTTPException(status_code=422, detail="不支持的审查模式。")
    final_path = _get_upload_path(body.uploadId)
    settings = get_settings()
    temp_dir = tempfile.TemporaryDirectory(prefix="bid-review-ul-")
    working_dir = Path(temp_dir.name)
    output_dir = working_dir / "output"
    run_id = start_review(final_path, output_dir, settings)
    return {"runId": run_id}


@router.get("/upload-review/{run_id}/status")
def upload_review_status(run_id: str) -> dict[str, object]:
    r = get_run(run_id)
    if not r:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    import time as _time
    elapsed = round(_time.time() - r["start_time"], 1)
    return {
        "runId": r["run_id"],
        "status": r["status"],
        "stage": r["stage"],
        "label": r["label"],
        "progress": r["progress"],
        "elapsed": elapsed,
        "error": r.get("error"),
    }


@router.get("/upload-review/{run_id}/result")
def upload_review_result(run_id: str) -> Response:
    r = get_run(run_id)
    if not r:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    if r["status"] == "error":
        raise HTTPException(status_code=500, detail=r.get("error", "Unknown error"))
    if r["status"] != "done":
        raise HTTPException(status_code=400, detail="Review not completed yet")
    path = get_result_path(run_id)
    if not path:
        raise HTTPException(status_code=500, detail="Result file not found")
    content = path.read_bytes()
    encoded_name = quote(r.get("filename") or path.name)
    cleanup_run(run_id)
    return Response(
        content=content, media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}"},
    )


def _get_upload_path(upload_id: str) -> Path:
    session = sessions.get(upload_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Upload session not found: {upload_id}")
    if session["status"] != "COMPLETED":
        raise HTTPException(status_code=400, detail="Upload not completed yet")
    path = UPLOAD_ROOT / "final" / f"{upload_id}-{session['file_name']}"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Merged file not found")
    return path
