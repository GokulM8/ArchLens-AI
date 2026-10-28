"""FastAPI routes for /v1/analyses. Contract: docs/API.md."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.analyses.errors import APIError
from app.analyses.service import AnalysisService

router = APIRouter(prefix="/v1/analyses", tags=["analyses"])


@lru_cache(maxsize=1)
def get_analysis_service() -> AnalysisService:
    """Process-wide service (shares the concurrency limit across requests)."""
    return AnalysisService.from_env()


class GitAnalysisRequest(BaseModel):
    kind: str
    source: Optional[str] = None


@router.post("", status_code=201)
async def create_analysis(
    request: Request, service: AnalysisService = Depends(get_analysis_service)
) -> Dict[str, Any]:
    content_type = request.headers.get("content-type", "")

    if content_type.startswith("application/json"):
        try:
            body = GitAnalysisRequest.model_validate(await request.json())
        except (ValueError, ValidationError) as e:
            raise APIError(422, "validation_error", f"Invalid request body: {e}")
        if body.kind == "git":
            raise APIError(
                501,
                "git_not_supported",
                "Analysing a Git URL is not supported yet. Download the repository as a ZIP and upload it.",
            )
        raise APIError(422, "validation_error", "JSON requests must use kind \"git\"; upload ZIPs as multipart.")

    if not content_type.startswith("multipart/form-data"):
        raise APIError(415, "unsupported_media_type", "Send a multipart/form-data upload with a 'file' field.")

    # Starlette spools the multipart body before we see it, so reject oversized
    # requests up front when the client declares a length (nginx enforces
    # client_max_body_size for chunked uploads in the Compose deployment).
    limit = service.limits.max_upload_bytes
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit + 64 * 1024:
        raise APIError(413, "upload_too_large", f"Upload exceeds the {limit // (1024 * 1024)} MB limit.")

    form = await request.form(max_files=1, max_fields=4)
    try:
        kind = form.get("kind", "zip")
        upload = form.get("file")
        if kind != "zip":
            raise APIError(422, "validation_error", "Field 'kind' must be \"zip\" for uploads.")
        if not isinstance(upload, UploadFile):
            raise APIError(422, "validation_error", "Missing 'file' field with a .zip archive.")
        filename = upload.filename or "repository.zip"
        if not filename.lower().endswith(".zip"):
            raise APIError(400, "invalid_archive", "Upload a .zip archive of your repository.")
        # The pipeline is CPU-bound and synchronous; keep it off the event loop.
        return await run_in_threadpool(service.analyze_zip, upload.file, filename)
    finally:
        await form.close()


@router.get("")
def list_analyses(
    limit: int = Query(50, ge=1, le=200),
    service: AnalysisService = Depends(get_analysis_service),
) -> Dict[str, Any]:
    return {"items": service.store.list(limit)}


@router.get("/{analysis_id}")
def get_analysis(analysis_id: str, service: AnalysisService = Depends(get_analysis_service)) -> Dict[str, Any]:
    return service.get(analysis_id)


@router.get("/{analysis_id}/graph")
def get_graph(analysis_id: str, service: AnalysisService = Depends(get_analysis_service)) -> Dict[str, Any]:
    return service.graph(analysis_id)


@router.get("/{analysis_id}/health")
def get_health(analysis_id: str, service: AnalysisService = Depends(get_analysis_service)) -> Dict[str, Any]:
    return service.health(analysis_id)


@router.get("/{analysis_id}/diff")
def get_diff(
    analysis_id: str,
    baseline: Optional[str] = Query(None, description="Analysis id to compare against (version A)"),
    service: AnalysisService = Depends(get_analysis_service),
) -> Dict[str, Any]:
    if not baseline:
        raise APIError(400, "missing_baseline", "Pass ?baseline=<analysisId> to compare two analyses.")
    return service.diff(analysis_id, baseline)


def install(app: FastAPI) -> None:
    """Mount the router and the /v1 error handlers on ``app``."""
    app.include_router(router)

    @app.exception_handler(APIError)
    async def _api_error(_: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(exc.body(), status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if not request.url.path.startswith("/v1/"):
            return await http_exception_handler(request, exc)
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(
            {"detail": str(exc.detail), "code": code}, status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        if not request.url.path.startswith("/v1/"):
            # Keep FastAPI's default shape for the existing /llm endpoints.
            return await request_validation_exception_handler(request, exc)
        return JSONResponse(
            {
                "detail": "Request validation failed.",
                "code": "validation_error",
                "errors": jsonable_encoder(exc.errors()),
            },
            status_code=422,
        )
