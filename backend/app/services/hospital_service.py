import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainValidationError, NotFound
from app.models import Hospital, HospitalInfo
from app.schemas.hospital import (
    HospitalCreate,
    HospitalInfoCreate,
    HospitalInfoOut,
    HospitalInfoUpdate,
    HospitalUpdate,
)
from app.services.common import apply_updates, paginate

MAX_INFO_RESULTS = 5
_WORD = re.compile(r"\w+", re.UNICODE)
_STOPWORDS = {
    "the", "and", "for", "are", "what", "when", "where", "how", "is", "do", "does", "you",
    "your", "can", "there", "any", "have", "has", "with", "about", "please", "tell", "me",
}  # fmt: skip


async def get_hospital(db: AsyncSession, hospital_id: uuid.UUID) -> Hospital:
    hospital = await db.get(Hospital, hospital_id)
    if hospital is None:
        raise NotFound("Hospital not found")
    return hospital


async def create_hospital(db: AsyncSession, data: HospitalCreate) -> Hospital:
    hospital = Hospital(**data.model_dump())
    db.add(hospital)
    await db.commit()
    await db.refresh(hospital)
    return hospital


async def list_hospitals(
    db: AsyncSession, *, limit: int = 50, offset: int = 0
) -> tuple[list[Hospital], int]:
    return await paginate(db, select(Hospital).order_by(Hospital.name), limit, offset)


async def update_hospital(
    db: AsyncSession, hospital_id: uuid.UUID, data: HospitalUpdate
) -> Hospital:
    hospital = await get_hospital(db, hospital_id)
    apply_updates(hospital, data.model_dump(exclude_unset=True))
    if hospital.closing_time <= hospital.opening_time:
        raise DomainValidationError("closing_time must be after opening_time")
    await db.commit()
    await db.refresh(hospital)
    return hospital


async def _get_info(db: AsyncSession, info_id: uuid.UUID) -> HospitalInfo:
    info = await db.get(HospitalInfo, info_id)
    if info is None:
        raise NotFound("Hospital info entry not found")
    return info


async def create_info(
    db: AsyncSession, hospital_id: uuid.UUID, data: HospitalInfoCreate
) -> HospitalInfo:
    await get_hospital(db, hospital_id)
    info = HospitalInfo(hospital_id=hospital_id, **data.model_dump())
    db.add(info)
    await db.commit()
    await db.refresh(info)
    return info


async def list_info(
    db: AsyncSession,
    hospital_id: uuid.UUID,
    *,
    category: str | None = None,
    include_inactive: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[HospitalInfo], int]:
    stmt = select(HospitalInfo).where(HospitalInfo.hospital_id == hospital_id)
    if category:
        stmt = stmt.where(HospitalInfo.category.ilike(category))
    if not include_inactive:
        stmt = stmt.where(HospitalInfo.is_active)
    stmt = stmt.order_by(HospitalInfo.category, HospitalInfo.question)
    return await paginate(db, stmt, limit, offset)


async def update_info(
    db: AsyncSession, info_id: uuid.UUID, data: HospitalInfoUpdate
) -> HospitalInfo:
    info = await _get_info(db, info_id)
    apply_updates(info, data.model_dump(exclude_unset=True))
    await db.commit()
    await db.refresh(info)
    return info


async def deactivate_info(db: AsyncSession, info_id: uuid.UUID) -> None:
    info = await _get_info(db, info_id)
    info.is_active = False
    await db.commit()


def _keywords(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.casefold()) if len(w) > 2 and w not in _STOPWORDS}


def _matches(word: str, haystack: set[str]) -> bool:
    if word in haystack:
        return True
    return len(word) >= 4 and any(
        len(h) >= 4 and (h.startswith(word) or word.startswith(h)) for h in haystack
    )


async def get_hospital_info(
    db: AsyncSession, hospital_id: uuid.UUID, query: str
) -> list[HospitalInfoOut]:
    entries = list(
        await db.scalars(
            select(HospitalInfo)
            .where(HospitalInfo.hospital_id == hospital_id, HospitalInfo.is_active)
            .order_by(HospitalInfo.category, HospitalInfo.question)
        )
    )
    words = _keywords(query)
    if not words:
        ranked = entries
    else:
        scored = []
        for entry in entries:
            haystack = _keywords(f"{entry.category} {entry.question} {entry.answer}")
            score = sum(_matches(w, haystack) for w in words)
            if score:
                scored.append((score, entry))
        scored.sort(key=lambda pair: -pair[0])
        ranked = [entry for _, entry in scored]
    return [HospitalInfoOut.model_validate(e) for e in ranked[:MAX_INFO_RESULTS]]
