"""Prediction API routes for ML operations."""

from typing import List

from fastapi import APIRouter, HTTPException

from app.models.prediction import PredictionCreate, PredictionResponse
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["predictions"])
prediction_service = PredictionService()


@router.post("/", response_model=PredictionResponse)
async def create_prediction(prediction: PredictionCreate):
    """Create and execute a prediction."""
    return await prediction_service.create_prediction(prediction, user_id=1)  # TODO: get from auth


@router.get("/{prediction_id}", response_model=PredictionResponse)
async def get_prediction(prediction_id: int):
    """Get a prediction by ID."""
    prediction = await prediction_service.get_prediction(prediction_id)
    if prediction is None:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return prediction


@router.get("/user/{user_id}", response_model=List[PredictionResponse])
async def get_user_predictions(user_id: int, skip: int = 0, limit: int = 100):
    """Get predictions for a user."""
    return await prediction_service.get_user_predictions(
        user_id=user_id, skip=skip, limit=limit
    )