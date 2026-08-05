from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.patient import PatientCreate, PatientResponse, PatientUpdate
from app.services.patient_service import (
    archive_patient,
    create_patient,
    get_patient,
    list_patients,
    update_patient,
)

router = APIRouter(prefix="/patients", tags=["patients"])

NOT_FOUND_DETAIL = "Patient not found"


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create patient",
)
def create_patient_route(
    patient_in: PatientCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatientResponse:
    return create_patient(db, current_user.id, patient_in)


@router.get("", response_model=list[PatientResponse], summary="List patients")
def list_patients_route(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PatientResponse]:
    return list_patients(db, current_user.id)


@router.get("/{patient_id}", response_model=PatientResponse)
def read_patient(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatientResponse:
    patient = get_patient(db, current_user.id, patient_id)

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )

    return patient


@router.patch("/{patient_id}", response_model=PatientResponse, summary="Update patient")
def patch_patient(
    patient_id: int,
    patient_in: PatientUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PatientResponse:
    patient = update_patient(db, current_user.id, patient_id, patient_in)

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )

    return patient


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Archive patient")
def archive_patient_route(
    patient_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    patient = archive_patient(db, current_user.id, patient_id)

    if patient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )
