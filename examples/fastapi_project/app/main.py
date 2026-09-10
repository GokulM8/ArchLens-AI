"""Main FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.routes import users, products, predictions
from app.services.database import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="ArchLens Example API",
    description="Example FastAPI application for ArchLens AI testing",
    version="1.0.0",
    lifespan=lifespan,
)

# Include routers
app.include_router(users.router, prefix="/api/v1")
app.include_router(products.router, prefix="/api/v1")
app.include_router(predictions.router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)