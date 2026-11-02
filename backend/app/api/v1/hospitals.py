import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession, Paging
from app.schemas.common import Page
from app.schemas.hospital import (
    HospitalCreate,
    HospitalInfoCreate,
    HospitalInfoOut,
    HospitalInfoUpdate,
    HospitalOut,
    HospitalUpdate,
)
from app.services import hospital_service

router = APIRouter(tags=["hospitals"])


@router.get("/hospitals")
async def list_hospitals(db: DbSession, paging: Paging) -> Page[HospitalOut]:
    items, total = await hospital_service.list_hospitals(
        db, limit=paging.limit, offset=paging.offset
    )
    return Page(
        items=[HospitalOut.model_validate(h) for h in items],
        total=total,
        limit=paging.limit,
        offset=paging.offset,
    )


@router.post("/hospitals", status_code=status.HTTP_201_CREATED)
async def create_hospital(db: DbSession, body: HospitalCreate) -> HospitalOut:
    return HospitalOut.model_validate(await hospital_service.create_hospital(db, body))


@router.get("/hospitals/{hospital_id}")
async def get_hospital(db: DbSession, hospital_id: uuid.UUID) -> HospitalOut:
    return HospitalOut.model_validate(await hospital_service.get_hospital(db, hospital_id))


@router.patch("/hospitals/{hospital_id}")
async def update_hospital(
    db: DbSession, hospital_id: uuid.UUID, body: HospitalUpdate
) -> HospitalOut:
    return HospitalOut.model_validate(await hospital_service.update_hospital(db, hospital_id, body))


@router.get("/hospitals/{hospital_id}/info", tags=["hospital info"])
async def list_info(
    db: DbSession,
    hospital_id: uuid.UUID,
    paging: Paging,
    category: str | None = None,
    include_inactive: Annotated[bool, Query()] = False,
) -> Page[HospitalInfoOut]:
    await hospital_service.get_hospital(db, hospital_id)
    items, total = await hospital_service.list_info(
        db,
        hospital_id,
        category=category,
        include_inactive=include_inactive,
        limit=paging.limit,
        offset=paging.offset,
    )
    return Page(
        items=[HospitalInfoOut.model_validate(i) for i in items],
        total=total,
        limit=paging.limit,
        offset=paging.offset,
    )


@router.post(
    "/hospitals/{hospital_id}/info", status_code=status.HTTP_201_CREATED, tags=["hospital info"]
)
async def create_info(
    db: DbSession, hospital_id: uuid.UUID, body: HospitalInfoCreate
) -> HospitalInfoOut:
    return HospitalInfoOut.model_validate(await hospital_service.create_info(db, hospital_id, body))


@router.patch("/info/{info_id}", tags=["hospital info"])
async def update_info(
    db: DbSession, info_id: uuid.UUID, body: HospitalInfoUpdate
) -> HospitalInfoOut:
    return HospitalInfoOut.model_validate(await hospital_service.update_info(db, info_id, body))


@router.delete("/info/{info_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["hospital info"])
async def delete_info(db: DbSession, info_id: uuid.UUID) -> None:
    """Soft delete: the entry is deactivated and hidden from the AI agent."""
    await hospital_service.deactivate_info(db, info_id)
