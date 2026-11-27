import logging
import time
from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app import crud
from app.config import get_settings
from app.database import get_db
from app.logging_config import configure_logging
from app.metrics import REQUEST_DURATION, REQUESTS
from app.models import Application, ApplicationStatus
from app.schemas import (
    ApplicationCreate,
    ApplicationList,
    ApplicationRead,
    ApplicationUpdate,
    ErrorResponse,
    LivenessResponse,
    ReadinessResponse,
)

settings = get_settings()
configure_logging(settings.log_level, sql_echo=settings.sql_echo)

logger = logging.getLogger(__name__)
request_logger = logging.getLogger("app.request")

QUIET_PATHS = {"/health/live", "/health/ready", "/favicon.ico", "/metrics"}

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Application not found"}}


app = FastAPI(title=settings.app_name)


@app.middleware("http")
async def observe_requests(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration = time.perf_counter() - start
        route = getattr(request.scope.get("route"), "path", "unmatched")
        REQUESTS.labels(method=request.method, route=route, status_code=str(status_code)).inc()
        REQUEST_DURATION.labels(method=request.method, route=route).observe(duration)

        if request.url.path in QUIET_PATHS:
            level = logging.DEBUG
        elif status_code >= 500:
            level = logging.WARNING
        else:
            level = logging.INFO
        request_logger.log(
            level,
            "%s %s %s",
            request.method,
            request.url.path,
            status_code,
            extra={
                "fields": {
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": status_code,
                    "duration_ms": round(duration * 1000, 2),
                }
            },
        )


@app.exception_handler(OperationalError)
async def database_unavailable_handler(request: Request, exc: OperationalError) -> JSONResponse:
    logger.error("Database error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Database unavailable, please try again later"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


DbSession = Annotated[Session, Depends(get_db)]


def get_application_or_404(application_id: int, db: DbSession) -> Application:
    application = crud.get_application(db, application_id)
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found",
        )
    return application


ApplicationDep = Annotated[Application, Depends(get_application_or_404)]


@app.get("/favicon.ico", status_code=status.HTTP_204_NO_CONTENT, include_in_schema=False)
def favicon() -> None:
    return None


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health/live", response_model=LivenessResponse, tags=["health"])
def liveness() -> dict:
    return {"status": "ok"}


@app.get(
    "/health/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse, "description": "Database unreachable"}},
    tags=["health"],
)
def readiness(db: DbSession, response: Response) -> dict:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("Readiness check failed: database unreachable", exc_info=True)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unavailable", "database": "unreachable"}
    return {"status": "ok", "database": "ok"}


@app.post(
    "/applications",
    response_model=ApplicationRead,
    status_code=status.HTTP_201_CREATED,
    tags=["applications"],
)
def create_application(data: ApplicationCreate, db: DbSession) -> Application:
    return crud.create_application(db, data)


@app.get("/applications", response_model=ApplicationList, tags=["applications"])
def list_applications(
    db: DbSession,
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    items, total = crud.list_applications(db, status=status_filter, offset=offset, limit=limit)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@app.get(
    "/applications/{application_id}",
    response_model=ApplicationRead,
    responses=NOT_FOUND,
    tags=["applications"],
)
def get_application(application: ApplicationDep) -> Application:
    return application


@app.patch(
    "/applications/{application_id}",
    response_model=ApplicationRead,
    responses=NOT_FOUND,
    tags=["applications"],
)
def update_application(data: ApplicationUpdate, application: ApplicationDep, db: DbSession) -> Application:
    return crud.update_application(db, application, data)


@app.delete(
    "/applications/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND,
    tags=["applications"],
)
def delete_application(application: ApplicationDep, db: DbSession) -> None:
    crud.delete_application(db, application)
