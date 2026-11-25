from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud
from app.config import get_settings
from app.database import Base, engine, get_db
from app.models import Application, ApplicationStatus
from app.schemas import ApplicationCreate, ApplicationList, ApplicationRead, ApplicationUpdate


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)  # Temporary: replaced by Alembic migrations on Day 2.
    yield


app = FastAPI(title=get_settings().app_name, lifespan=lifespan)

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


@app.get("/applications/{application_id}", response_model=ApplicationRead)
def get_application(application: ApplicationDep) -> Application:
    return application


@app.patch("/applications/{application_id}", response_model=ApplicationRead)
def update_application(data: ApplicationUpdate, application: ApplicationDep, db: DbSession) -> Application:
    return crud.update_application(db, application, data)


@app.delete("/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application: ApplicationDep, db: DbSession) -> None:
    crud.delete_application(db, application)
