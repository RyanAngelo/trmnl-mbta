from typing import Optional
from pydantic import BaseModel, field_validator

from src.mbta.constants import VALID_ROUTE_PATTERN

class RouteConfig(BaseModel):
    """Configuration model for a single route"""
    route_id: str

    @field_validator("route_id")
    @classmethod
    def validate_route_id(cls, v):
        """Validate route_id format"""
        if not VALID_ROUTE_PATTERN.match(v):
            raise ValueError("Invalid route_id format")
        return v

class Prediction(BaseModel):
    """Schedule prediction model"""
    route_id: str
    stop_id: str
    arrival_time: Optional[str]
    departure_time: Optional[str]
    direction_id: int
    status: Optional[str] 