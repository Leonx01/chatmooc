from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.v1.routes.auth import get_current_user
from app.models import Users
from app.schema.resources import (
    ResourceGetIn,
    ResourceGetResponse,
    ResourceListResponse,
    ResourceOut,
    ResourceParseResponse,
    ResourceUploadIn,
    ResourceUploadResponse,
)
from app.service.resource_service import ResourceService, get_resource_service

router = APIRouter(prefix="/resources", tags=["resources"])


@router.post("/upload", response_model=ResourceUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_resource(
    payload: ResourceUploadIn = Depends(ResourceUploadIn.as_form),
    current_user: Users = Depends(get_current_user),
    resource_service: ResourceService = Depends(get_resource_service),
) -> ResourceUploadResponse:
    resource = await resource_service.create_from_upload(
        uid=current_user.uid,
        file=payload.file,
        rname=payload.rname,
        rtype=payload.rtype,
    )
    return ResourceUploadResponse(
        resource=ResourceOut.from_orm_with_url(resource, resource_service.resolve_url(resource))
    )


@router.get("", response_model=ResourceListResponse)
async def list_resources(
    current_user: Users = Depends(get_current_user),
    resource_service: ResourceService = Depends(get_resource_service),
) -> ResourceListResponse:
    resources = await resource_service.list_by_uid(current_user.uid)
    return ResourceListResponse(
        items=[ResourceOut.from_orm_with_url(r, resource_service.resolve_url(r)) for r in resources]
    )


@router.get("/{rid}", response_model=ResourceGetResponse)
async def get_resource(
    params: ResourceGetIn = Depends(ResourceGetIn.from_path),
    current_user: Users = Depends(get_current_user),
    resource_service: ResourceService = Depends(get_resource_service),
) -> ResourceGetResponse:
    resource = await resource_service.get_by_rid(params.rid)
    if not resource or resource.uid != current_user.uid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资源不存在")
    return ResourceGetResponse(
        resource=ResourceOut.from_orm_with_url(resource, resource_service.resolve_url(resource))
    )


@router.post("/{rid}/parse", response_model=ResourceParseResponse)
async def parse_resource(
    params: ResourceGetIn = Depends(ResourceGetIn.from_path),
    current_user: Users = Depends(get_current_user),
    resource_service: ResourceService = Depends(get_resource_service),
    force: bool = Query(default=False, description="是否强制重新解析"),
) -> ResourceParseResponse:
    resource = await resource_service.get_by_rid(params.rid)
    if not resource or resource.uid != current_user.uid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资源不存在")

    result = await resource_service.parse_resource(rid=params.rid, force=force)
    return ResourceParseResponse(**result)
