from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=settings.app_version,
        checks={"process": "ok"},
    )


@router.get("/health/ready", response_model=HealthResponse)
async def readiness(response: Response) -> HealthResponse:
    settings = get_settings()
    checks = {"configuration": "ok"}
    health_status = "ok"

    if settings.readiness_check_dependencies:
        checks["postgres"] = "not_configured"
        checks["redis"] = "not_configured"
        health_status = "degraded"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=health_status,
        service=settings.app_name,
        version=settings.app_version,
        checks=checks,
    )


@router.get("/health/deepseek")
async def deepseek_test() -> dict[str, object]:
    settings = get_settings()
    if not settings.deepseek_api_key:
        return {"status": "error", "message": "API key not configured"}
    try:
        from app.pipeline.llm_agent import DeepSeekAgent
        from app.pipeline.splitter import Section
        agent = DeepSeekAgent(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
        )
        section = Section(heading="test", content="投标人：测试公司", start_page=1, end_page=1)
        result = agent.extract(section)
        return {"status": "ok", "facts": len(result.get("facts", [])), "model": settings.deepseek_model}
    except Exception as exc:
        return {"status": "error", "message": str(exc), "type": type(exc).__name__}
