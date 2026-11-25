from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Application, ApplicationStatus
from app.schemas import ApplicationCreate, ApplicationUpdate


def create_application(db: Session, data: ApplicationCreate) -> Application:
    application = Application(**data.model_dump())
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def get_application(db: Session, application_id: int) -> Application | None:
    return db.get(Application, application_id)


def list_applications(
    db: Session,
    status: ApplicationStatus | None = None,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Application], int]:
    query = select(Application)
    if status is not None:
        query = query.where(Application.status == status)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    items = db.scalars(
        query.order_by(Application.applied_date.desc(), Application.id.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(items), total


def update_application(db: Session, application: Application, data: ApplicationUpdate) -> Application:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(application, field, value)
    db.commit()
    db.refresh(application)
    return application


def delete_application(db: Session, application: Application) -> None:
    db.delete(application)
    db.commit()
