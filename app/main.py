import logging
import time
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.guards import limiter
from app.llm import SchemaValidationFailed, UpstreamUnavailable
from app.routers import bias, compliance, hallucination

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("governance_api.access")

app = FastAPI(title="governance-api", version="1.0.0")
app.state.limiter = limiter


# CORS middleware with explicit origins list (no wildcards)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.middleware("http")
async def privacy_logging_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000, 2)
    timestamp = datetime.now(timezone.utc).isoformat()
    # Privacy commitment: log ONLY timestamp, path, status, duration.
    logger.info(f"[{timestamp}] PATH={request.url.path} STATUS={response.status_code} DURATION={duration_ms}ms")
    return response


@app.exception_handler(RateLimitExceeded)
async def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={"detail": "Rate limit exceeded. Maximum 5 requests per hour allowed."}
    )


@app.exception_handler(RequestValidationError)
async def custom_validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Input validation failed. Ensure text length <= 2000 chars."}
    )


@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(UpstreamUnavailable)
async def custom_upstream_handler(request: Request, exc: UpstreamUnavailable):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Upstream LLM provider is currently unavailable."}
    )


@app.exception_handler(SchemaValidationFailed)
async def custom_schema_handler(request: Request, exc: SchemaValidationFailed):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Model response validation failed."}
    )


@app.exception_handler(Exception)
async def custom_unhandled_exception_handler(request: Request, exc: Exception):
    import traceback
    timestamp = datetime.now(timezone.utc).isoformat()
    tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    logger.error(f"[{timestamp}] PATH={request.url.path} UNHANDLED_EXCEPTION ({type(exc).__name__}):\n{tb_str}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred."}
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/debug-crash")
async def debug_crash(request: Request):
    """Debug route for privacy canary 500 test (active only when DEBUG=True)."""
    if not settings.DEBUG:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    raise RuntimeError("Simulated crash for privacy canary test")


app.include_router(bias.router)
app.include_router(compliance.router)
app.include_router(hallucination.router)
