"""Prediction model for ML-based predictions."""

from datetime import datetime
from typing import Optional, List
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class PredictionType(str, Enum):
    """Type of prediction."""

    RECOMMENDATION = "recommendation"
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    ANOMALY_DETECTION = "anomaly_detection"


class PredictionStatus(str, Enum):
    """Prediction status."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class Prediction(Base):
    """SQLAlchemy Prediction model."""

    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    prediction_type = Column(String(50), nullable=False)
    input_data = Column(Text, nullable=False)  # JSON serialized input
    output_data = Column(Text, nullable=True)  # JSON serialized output
    confidence = Column(Float, nullable=True)
    status = Column(String(20), default=PredictionStatus.PENDING.value)
    model_version = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationship
    user = relationship("User", back_populates="predictions")


class PredictionBase(BaseModel):
    """Base Pydantic model for Prediction."""

    prediction_type: PredictionType
    input_data: dict
    model_version: Optional[str] = None


class PredictionCreate(PredictionBase):
    """Prediction creation model."""
    pass


class PredictionResponse(PredictionBase):
    """Prediction response model."""

    id: int
    user_id: int
    output_data: Optional[dict] = None
    confidence: Optional[float] = None
    status: PredictionStatus
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True