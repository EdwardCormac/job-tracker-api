from datetime import date, datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, PlainSerializer, model_validator

from app.models import ApplicationStatus

JobUrl = Annotated[HttpUrl, PlainSerializer(str, return_type=str)]


class ApplicationBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    status: ApplicationStatus = ApplicationStatus.applied
    job_url: JobUrl | None = None
    applied_date: date = Field(default_factory=date.today)
    notes: str | None = None


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    company: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = Field(default=None, min_length=1, max_length=200)
    status: ApplicationStatus | None = None
    job_url: JobUrl | None = None
    applied_date: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def reject_null_for_required_fields(self) -> Self:
        for field in ("company", "role", "status", "applied_date"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ApplicationRead(ApplicationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ApplicationList(BaseModel):
    items: list[ApplicationRead]
    total: int
    limit: int
    offset: int


class ErrorResponse(BaseModel):
    detail: str
