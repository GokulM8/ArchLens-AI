"""ArchLens Architecture Copilot — FastAPI integration (Phase 6.15).

Exposes the LLM operations over HTTP so clients (UI, CI, scripts) can reach the
Architecture Copilot. The deterministic engine is still the source of truth:
every endpoint reasons only over verified ArchLens artifacts.

The artifacts directory is configured with ``ARCHLENS_ARTIFACTS_DIR``
(defaults to ``output``), and the LLM provider via the ``ARCHLENS_LLM_*`` env
vars. When no LLM provider is configured, operations return a structured
``LLMOperationResponse`` with ``success=false`` and a clear error — never a
crash, and the deterministic pipeline is unaffected.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, Optional
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field

from app.llm.context import VerifiedContextBuilder
from app.llm.guardrails import GroundingGuardrails
from app.llm.factory import LLMProviderFactory
from app.llm.service import LLMService


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class AskRequest(BaseModel):
    """Body for the /llm/ask endpoint."""
    question: str = Field(..., min_length=1)
    user_context: Optional[Dict[str, Any]] = None
    conversation_id: Optional[str] = None


class ExplainRequest(BaseModel):
    """Body for target-based explain endpoints."""
    target: str = Field(..., min_length=1)
    user_context: Optional[Dict[str, Any]] = None
    conversation_id: Optional[str] = None


class DependencyRequest(BaseModel):
    """Body for the /llm/dependency endpoint."""
    source: str = Field(..., min_length=1)
    target: str = Field(..., min_length=1)
    user_context: Optional[Dict[str, Any]] = None
    conversation_id: Optional[str] = None


class ConversationRequest(BaseModel):
    """Body for POST /llm/conversations."""
    repository: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Service wiring
# ---------------------------------------------------------------------------


def get_artifacts_dir() -> Path:
    """Resolve the artifacts directory (env override, else ./output)."""
    return Path(os.getenv("ARCHLENS_ARTIFACTS_DIR", "output"))


def _build_llm_service(artifacts_dir: Path) -> LLMService:
    """Construct an LLMService over the configured artifacts directory."""
    if not artifacts_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Artifacts directory not found: {artifacts_dir}. Run `archlens analyze` first.",
        )
    context_builder = VerifiedContextBuilder.from_artifacts_dir(artifacts_dir)
    guardrails = GroundingGuardrails(context_builder)
    return LLMService(LLMProviderFactory, context_builder, guardrails)


@lru_cache(maxsize=4)
def get_llm_service(artifacts_dir: Path) -> LLMService:
    """
    App-scoped LLMService for a given artifacts directory.

    Cached so that in-memory conversation state survives across HTTP requests
    inside the same process. Tests may cache fresh instances per directory.
    """
    return _build_llm_service(artifacts_dir)


def get_llm_service_for_request(
    artifacts_dir: Path = Depends(get_artifacts_dir),
) -> LLMService:
    """FastAPI dependency wrapper that resolves the artifacts dir, then the service."""
    return get_llm_service(artifacts_dir)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create the ArchLens Architecture Copilot FastAPI application."""
    app = FastAPI(
        title="ArchLens Architecture Copilot",
        description="LLM explanations and reasoning over deterministic ArchLens artifacts.",
        version="0.1.0",
    )

    @app.get("/health")
    def health() -> Dict[str, Any]:
        """Simple liveness/config probe. LLM is optional."""
        return {
            "status": "ok",
            "llm_configured": LLMProviderFactory.is_configured(),
            "artifacts_dir": str(get_artifacts_dir()),
        }

    @app.get("/llm/status")
    def llm_status() -> Dict[str, Any]:
        """Report LLM provider configuration status without leaking secrets."""
        error = LLMProviderFactory.get_configuration_error()
        return {
            "configured": LLMProviderFactory.is_configured(),
            "provider": os.getenv("ARCHLENS_LLM_PROVIDER", ""),
            "model": os.getenv("ARCHLENS_LLM_MODEL", ""),
            "configuration_error": error,
        }

    @app.post("/llm/explain")
    async def llm_explain(service: LLMService = Depends(get_llm_service_for_request)) -> Any:
        """Explain the overall repository architecture."""
        return await service.explain_architecture({})

    @app.post("/llm/ask")
    async def llm_ask(req: AskRequest, service: LLMService = Depends(get_llm_service_for_request)) -> Any:
        """Answer an architecture question from the deterministic artifacts."""
        return await service.ask(
            req.question,
            user_context=req.user_context,
            conversation_id=req.conversation_id,
        )

    @app.post("/llm/component")
    async def llm_component(req: ExplainRequest, service: LLMService = Depends(get_llm_service_for_request)) -> Any:
        """Explain a specific component."""
        return await service.explain_component(
            req.target,
            user_context=req.user_context,
            conversation_id=req.conversation_id,
        )

    @app.post("/llm/dependency")
    async def llm_dependency(req: DependencyRequest, service: LLMService = Depends(get_llm_service_for_request)) -> Any:
        """Explain the dependency between two components."""
        return await service.explain_dependency(
            req.source,
            req.target,
            user_context=req.user_context,
            conversation_id=req.conversation_id,
        )

    @app.post("/llm/risk")
    async def llm_risk(req: ExplainRequest, service: LLMService = Depends(get_llm_service_for_request)) -> Any:
        """Explain an architectural risk."""
        return await service.explain_risk(
            req.target,
            user_context=req.user_context,
            conversation_id=req.conversation_id,
        )

    @app.post("/llm/recommendation")
    async def llm_recommendation(req: ExplainRequest, service: LLMService = Depends(get_llm_service_for_request)) -> Any:
        """Explain an evolution recommendation."""
        return await service.explain_recommendation(
            req.target,
            user_context=req.user_context,
            conversation_id=req.conversation_id,
        )

    @app.post("/llm/impact")
    async def llm_impact(req: ExplainRequest, service: LLMService = Depends(get_llm_service_for_request)) -> Any:
        """Analyze the impact of changing a component."""
        return await service.explain_impact(
            req.target,
            user_context=req.user_context,
            conversation_id=req.conversation_id,
        )

    @app.post("/llm/refactor-plan")
    async def llm_refactor_plan(req: ExplainRequest, service: LLMService = Depends(get_llm_service_for_request)) -> Any:
        """Generate a refactoring plan for a recommendation."""
        return await service.generate_refactoring_plan(
            req.target,
            user_context=req.user_context,
            conversation_id=req.conversation_id,
        )

    @app.post("/llm/summary")
    async def llm_summary(service: LLMService = Depends(get_llm_service_for_request)) -> Any:
        """Summarize the repository architecture."""
        return await service.summarize_repository({})

    @app.post("/llm/conversations")
    def create_conversation(
        req: ConversationRequest,
        service: LLMService = Depends(get_llm_service_for_request),
    ) -> Any:
        """Start a conversation for multi-turn follow-ups."""
        return service.create_conversation(repository=req.repository)

    @app.get("/llm/conversations/{conversation_id}")
    def get_conversation(
        conversation_id: str,
        service: LLMService = Depends(get_llm_service_for_request),
    ) -> Any:
        """Retrieve a conversation and its history."""
        conversation = service.get_conversation(conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation

    return app


app = create_app()