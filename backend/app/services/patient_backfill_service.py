"""Backfills patient_id on Medication, ClinicalDocument, and Analysis for
records created before Patient existed (Sprint 3.5, Issue #128: Migrate
Database to Support Patients).

Called from the Alembic migration that adds the patient_id columns, and
exercised directly by tests using the same `db` session fixture every other
service test in this project already uses. Kept in `app/services/` rather
than inline in the migration file so the same logic isn't duplicated
between the two, and so it can be unit-tested normally.

This intentionally uses the live ORM models (Patient, Medication,
ClinicalDocument, Analysis, User) rather than ad-hoc SQLAlchemy Core table
shadows. The usual reason to avoid that in a migration - protecting the
migration from later, unrelated model changes - doesn't apply here, since
this module exists specifically to backfill the very columns these models
gain in this same change. The trade-off: if any of these five models is
later renamed or restructured, this module (and the migration that calls
it) would need updating too, or would fail if ever replayed from scratch
against an empty database. Documented as a known limitation, not an
oversight.
"""

from datetime import date

from sqlalchemy.orm import Session

from app.models.analysis import Analysis
from app.models.clinical_document import ClinicalDocument
from app.models.medication import Medication
from app.models.patient import Patient
from app.models.user import User

ACTIVE_STATUS = "active"

LEGACY_PATIENT_FIRST_NAME = "Legacy"
LEGACY_PATIENT_LAST_NAME = "Patient"
LEGACY_PATIENT_DATE_OF_BIRTH = date(1900, 1, 1)
LEGACY_PATIENT_NOTES = "Automatically created during patient migration."

# Every model that gains a patient_id column in this migration. Order
# doesn't affect correctness (each is backfilled independently per user),
# but is kept stable for readability and deterministic test output.
_LEGACY_MODELS = (Medication, ClinicalDocument, Analysis)


class AmbiguousPatientBackfillError(Exception):
    """Raised when a user has legacy resources to backfill but more than one
    active Patient, so there is no safe way to guess which one owns them.
    Manual intervention (archiving or merging the extra patients, or setting
    patient_id by hand) is required before this migration can proceed for
    that user.
    """

    def __init__(self, user_id: int, active_patient_ids: list[int]):
        self.user_id = user_id
        self.active_patient_ids = active_patient_ids
        super().__init__(
            f"Cannot backfill patient_id for user {user_id}: {len(active_patient_ids)} "
            f"active patients exist ({active_patient_ids}) and this user has legacy "
            "medications, clinical documents, or analyses that need a patient assigned. "
            "Refusing to guess which patient owns them - resolve manually (archive the "
            "extra patients, or set patient_id by hand for this user's legacy records) "
            "and re-run this migration."
        )


def _legacy_rows(db: Session, model, user_id: int):
    return db.query(model).filter(model.user_id == user_id, model.patient_id.is_(None)).all()


def _create_legacy_patient(db: Session, user_id: int) -> Patient:
    patient = Patient(
        user_id=user_id,
        first_name=LEGACY_PATIENT_FIRST_NAME,
        last_name=LEGACY_PATIENT_LAST_NAME,
        date_of_birth=LEGACY_PATIENT_DATE_OF_BIRTH,
        external_mrn=None,
        status=ACTIVE_STATUS,
        notes=LEGACY_PATIENT_NOTES,
    )
    db.add(patient)
    db.flush()  # assigns patient.id without committing the surrounding transaction

    return patient


def _assert_no_orphans(db: Session) -> None:
    for model in _LEGACY_MODELS:
        orphan_count = db.query(model).filter(model.patient_id.is_(None)).count()

        if orphan_count:
            raise RuntimeError(
                f"{orphan_count} {model.__tablename__} row(s) still have no patient_id "
                "after backfill - this indicates a bug in the backfill logic itself."
            )


def backfill_patient_ids(db: Session) -> None:
    """For every user with at least one legacy (patient_id IS NULL)
    medication, clinical document, or analysis: assigns them all to that
    user's sole active Patient, or a newly created placeholder Patient if
    they have none. Raises AmbiguousPatientBackfillError, without changing
    anything for that user, if more than one active Patient exists.

    Never commits - the caller (the Alembic migration, or a test using the
    `db` fixture) owns the transaction boundary, so a failure partway
    through can be rolled back as a whole, leaving the database exactly as
    it was before this ran.

    Idempotent: re-running finds nothing left to backfill for a user
    already processed (every legacy row already has a patient_id, so
    _legacy_rows returns nothing), and never creates a second placeholder
    Patient for the same user, since that user now has exactly one active
    Patient rather than zero.
    """
    for user in db.query(User).order_by(User.id).all():
        legacy_by_model = {model: _legacy_rows(db, model, user.id) for model in _LEGACY_MODELS}

        if not any(legacy_by_model.values()):
            continue

        active_patients = (
            db.query(Patient)
            .filter(Patient.user_id == user.id, Patient.status == ACTIVE_STATUS)
            .order_by(Patient.id)
            .all()
        )

        if len(active_patients) > 1:
            raise AmbiguousPatientBackfillError(user.id, [patient.id for patient in active_patients])

        target_patient = active_patients[0] if active_patients else _create_legacy_patient(db, user.id)

        for rows in legacy_by_model.values():
            for row in rows:
                row.patient_id = target_patient.id

    db.flush()
    _assert_no_orphans(db)


def clear_patient_ids(db: Session) -> None:
    """Downgrade counterpart to backfill_patient_ids: nulls patient_id back
    out on all three tables. Deliberately does not delete any placeholder
    Patient rows backfill_patient_ids created - by the time this runs they
    are ordinary, real Patient rows (editable through the Patient API), and
    deleting them is a much riskier, less reversible operation than simply
    unsetting a foreign key.
    """
    for model in _LEGACY_MODELS:
        db.query(model).update({model.patient_id: None})

    db.flush()
