import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import get_settings

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)
app.include_router(api_router, prefix=settings.api_prefix)


class RequestIdMiddleware:
    def __init__(self, asgi_app: Any) -> None:
        self.app = asgi_app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        request_id = headers.get(b"x-request-id", str(uuid.uuid4()).encode()).decode()
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append(
                    (b"x-request-id", request_id.encode("ascii", errors="ignore"))
                )
            await send(message)

        await self.app(scope, receive, send_with_request_id)


app.add_middleware(RequestIdMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "请求参数校验失败",
                "request_id": request_id,
                "details": {"errors": exc.errors()},
            }
        },
    )


frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
if frontend_dir.is_dir():
    frontend_html = (frontend_dir / "index.html").read_text(encoding="utf-8")

    @app.get("/", include_in_schema=False, response_class=HTMLResponse)
    async def frontend_index() -> HTMLResponse:
        return HTMLResponse(frontend_html)

    app.mount(
        "/frontend",
        StaticFiles(directory=frontend_dir),
        name="frontend-assets",
    )
