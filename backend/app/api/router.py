from fastapi import APIRouter, Depends

from app.api.deps import require_staff, require_staff_or_service
from app.api.v1 import appointments, auth, calls, doctors, health, hospitals, patients, slots

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)

protected = APIRouter(dependencies=[Depends(require_staff)])
protected.include_router(hospitals.router)
protected.include_router(doctors.router)
protected.include_router(slots.router)
protected.include_router(patients.router)
protected.include_router(appointments.router)

api_router.include_router(protected)

api_router.include_router(calls.router, dependencies=[Depends(require_staff_or_service)])
