from fastapi import APIRouter, Depends

from app.api.deps import require_staff
from app.api.v1 import appointments, auth, calls, doctors, health, hospitals, patients, slots

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)

# include_router copies routes, so every protected module is added before `protected`
# itself is included below.
protected = APIRouter(dependencies=[Depends(require_staff)])
protected.include_router(hospitals.router)
protected.include_router(doctors.router)
protected.include_router(slots.router)
protected.include_router(patients.router)
protected.include_router(appointments.router)
protected.include_router(calls.router)

api_router.include_router(protected)
