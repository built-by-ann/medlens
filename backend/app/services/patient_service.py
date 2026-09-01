from sqlalchemy.orm import Session

from app.models.patient import Patient
from app.schemas.patient import PatientCreate, PatientUpdate

ARCHIVED_STATUS = "archived"


def create_patient(db: Session, user_id: int, patient_in: PatientCreate) -> Patient:
    patient = Patient(
        user_id=user_id,
        first_name=patient_in.first_name,
        last_name=patient_in.last_name,
        date_of_birth=patient_in.date_of_birth,
        external_mrn=patient_in.external_mrn,
        notes=patient_in.notes,
    )

    db.add(patient)
    db.commit()
    db.refresh(patient)

    return patient


def list_patients(db: Session, user_id: int) -> list[Patient]:
    # Archived patients are excluded from the default list; archiving is a
    # soft delete, and an archived chart shouldn't clutter the provider's
    # normal patient list. get_patient() below has no such filter, since an
    # archived patient's own detail view should still be reachable directly.
    return (
        db.query(Patient)
        .filter(
            Patient.user_id == user_id,
            Patient.status != ARCHIVED_STATUS,
        )
        .order_by(Patient.created_at.desc())
        .all()
    )


def get_patient(db: Session, user_id: int, patient_id: int) -> Patient | None:
    return (
        db.query(Patient)
        .filter(
            Patient.id == patient_id,
            Patient.user_id == user_id,
        )
        .first()
    )


def update_patient(
    db: Session, user_id: int, patient_id: int, patient_in: PatientUpdate
) -> Patient | None:
    patient = get_patient(db, user_id, patient_id)

    if patient is None:
        return None

    updates = patient_in.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(patient, field, value)

    db.commit()
    db.refresh(patient)

    return patient


def archive_patient(db: Session, user_id: int, patient_id: int) -> Patient | None:
    patient = get_patient(db, user_id, patient_id)

    if patient is None:
        return None

    patient.status = ARCHIVED_STATUS

    db.commit()
    db.refresh(patient)

    return patient
