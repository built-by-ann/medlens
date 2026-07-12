from sqlalchemy.orm import Session

from app.models.medication import Medication
from app.schemas.medication import MedicationCreate, MedicationUpdate


def create_medication(db: Session, user_id: int, medication_in: MedicationCreate) -> Medication:
    medication = Medication(
        user_id=user_id,
        medication_name=medication_in.medication_name,
        dose=medication_in.dose,
        route=medication_in.route,
        frequency=medication_in.frequency,
        status=medication_in.status,
        source=medication_in.source,
        notes=medication_in.notes,
    )

    db.add(medication)
    db.commit()
    db.refresh(medication)

    return medication


def get_medications_for_user(db: Session, user_id: int) -> list[Medication]:
    return (
        db.query(Medication)
        .filter(Medication.user_id == user_id)
        .order_by(Medication.created_at.desc())
        .all()
    )


def get_medication(db: Session, user_id: int, medication_id: int) -> Medication | None:
    return (
        db.query(Medication)
        .filter(
            Medication.id == medication_id,
            Medication.user_id == user_id,
        )
        .first()
    )


def update_medication(
    db: Session, user_id: int, medication_id: int, medication_in: MedicationUpdate
) -> Medication | None:
    medication = get_medication(db, user_id, medication_id)

    if medication is None:
        return None

    updates = medication_in.model_dump(exclude_unset=True)

    for field, value in updates.items():
        setattr(medication, field, value)

    db.commit()
    db.refresh(medication)

    return medication


def delete_medication(db: Session, user_id: int, medication_id: int) -> bool:
    medication = get_medication(db, user_id, medication_id)

    if medication is None:
        return False

    db.delete(medication)
    db.commit()

    return True
