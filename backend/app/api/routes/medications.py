from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.medication import MedicationCreate, MedicationResponse, MedicationUpdate
from app.services.medication_service import (
    create_medication,
    delete_medication,
    get_medication,
    get_medications_for_user,
    update_medication,
)

router = APIRouter(prefix="/medications", tags=["medications"])

NOT_FOUND_DETAIL = "Medication not found"


@router.post(
    "",
    response_model=MedicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_medication_route(
    medication_in: MedicationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MedicationResponse:
    return create_medication(db, current_user.id, medication_in)


@router.get("", response_model=list[MedicationResponse])
def list_medications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MedicationResponse]:
    return get_medications_for_user(db, current_user.id)


@router.get("/{medication_id}", response_model=MedicationResponse)
def read_medication(
    medication_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MedicationResponse:
    medication = get_medication(db, current_user.id, medication_id)

    if medication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )

    return medication


@router.patch("/{medication_id}", response_model=MedicationResponse)
def patch_medication(
    medication_id: int,
    medication_in: MedicationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MedicationResponse:
    medication = update_medication(db, current_user.id, medication_id, medication_in)

    if medication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )

    return medication


@router.delete("/{medication_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_medication(
    medication_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    deleted = delete_medication(db, current_user.id, medication_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )
