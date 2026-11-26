import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app import crud
from app.config import get_settings
from app.database import get_db
from app.models import Application, ApplicationStatus
from app.schemas import (
    ApplicationCreate,
    ApplicationList,
    ApplicationRead,
    ApplicationUpdate,
    ErrorResponse,
)

logger = logging.getLogger(__name__)

NOT_FOUND = {404: {"model": ErrorResponse, "description": "Application not found"}}


app = FastAPI(title=get_settings().app_name)


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


@app.post("/applications", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application(data: ApplicationCreate, db: DbSession) -> Application:
    return crud.create_application(db, data)


@app.get("/applications", response_model=ApplicationList)
def list_applications(
    db: DbSession,
    status_filter: Annotated[ApplicationStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    items, total = crud.list_applications(db, status=status_filter, offset=offset, limit=limit)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@app.get("/applications/{application_id}", response_model=ApplicationRead, responses=NOT_FOUND)
def get_application(application: ApplicationDep) -> Application:
    return application


@app.patch("/applications/{application_id}", response_model=ApplicationRead, responses=NOT_FOUND)
def update_application(data: ApplicationUpdate, application: ApplicationDep, db: DbSession) -> Application:
    return crud.update_application(db, application, data)


@app.delete(
    "/applications/{application_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=NOT_FOUND,
)
def delete_application(application: ApplicationDep, db: DbSession) -> None:
    crud.delete_application(db, application)
