from fastapi import Depends, FastAPI, HTTPException, Request, Security
from fastapi.security import APIKeyHeader
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.mbta.config import safe_load_config, safe_save_config
from src.mbta.constants import API_KEY
from src.mbta.models import RouteConfig

# Configure rate limiter
limiter = Limiter(key_func=get_remote_address)

# API Security
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Security(api_key_header)):
    """Verify the API key."""
    if not API_KEY:
        return  # Skip validation if API_KEY is not set
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if api_key != API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key

def setup_routes(app: FastAPI):
    """Set up FastAPI routes."""
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    @app.get("/config", response_model=RouteConfig)
    @limiter.limit("60/minute")
    async def get_config(request: Request, api_key: str = Depends(verify_api_key)):
        """Get current configuration."""
        return safe_load_config()

    @app.post("/config")
    @limiter.limit("10/minute")
    async def update_config(
        config: RouteConfig, request: Request, api_key: str = Depends(verify_api_key)
    ):
        """Update configuration."""
        safe_save_config(config)
        return {"status": "success"} 