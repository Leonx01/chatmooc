from __future__ import annotations

import datetime
from typing import Optional

from fastapi import File, Form, Path, UploadFile
from pydantic import BaseModel, ConfigDict


class ResourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rid: str
    uid: str
    rname: str
    rtype: str

    # Derived by API from storage_provider/storage_key or falls back to legacy url.
    url: str

    storage_provider: Optional[str] = None
    storage_key: Optional[str] = None

    status: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    @classmethod
    def from_orm_with_url(cls, resource: object, url: str) -> "ResourceOut":
        """
        Build response DTO from an ORM object, while allowing callers to inject a derived `url`.

        We keep URL derivation outside the schema to avoid coupling schema to storage/service layers.
        """
        base = cls.model_validate(resource)
        return base.model_copy(update={"url": url})


class ResourceUploadResponse(BaseModel):
    resource: ResourceOut


class ResourceListResponse(BaseModel):
    items: list[ResourceOut]


class ResourceGetResponse(BaseModel):
    resource: ResourceOut


class ResourceParseResponse(BaseModel):
    rid: str
    task_id: Optional[str] = None
    status: str
    message: Optional[str] = None


class ResourceUploadIn(BaseModel):
    """
    Multipart upload payload.

    FastAPI can't parse `UploadFile` inside a JSON body; this model is populated via `Depends(as_form)`.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    file: UploadFile
    rtype: str = "doc"
    rname: Optional[str] = None

    @classmethod
    def as_form(
        cls,
        file: UploadFile = File(...),
        rtype: str = Form("doc"),
        rname: Optional[str] = Form(None),
    ) -> "ResourceUploadIn":
        return cls(file=file, rtype=rtype, rname=rname)


class ResourceGetIn(BaseModel):
    rid: str

    @classmethod
    def from_path(cls, rid: str = Path(...)) -> "ResourceGetIn":
        return cls(rid=rid)
