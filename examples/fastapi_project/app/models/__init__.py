"""Database models for the example application."""

from app.models.user import User
from app.models.product import Product
from app.models.prediction import Prediction

__all__ = ["User", "Product", "Prediction"]