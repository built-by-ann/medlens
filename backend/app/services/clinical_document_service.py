from sqlalchemy.orm import Session

from app.models.clinical_document import ClinicalDocument
from app.models.patient import Patient
from app.schemas.clinical_document import ClinicalDocumentCreate

DEFAULT_FILE_TYPE = "manual_entry"
TXT_FILE_TYPE = "txt"
PDF_FILE_TYPE = "pdf"


def create_clinical_document(
    db: Session, patient: Patient, document_in: ClinicalDocumentCreate
) -> ClinicalDocument:
    document = ClinicalDocument(
        patient_id=patient.id,
        # user_id is retained temporarily (Sprint 3.5 migration period) and
        # is still NOT NULL at the database level, so every create must
        # still populate it. Deriving it from the already-resolved,
        # already-ownership-checked Patient - rather than accepting it as a
        # separate parameter - guarantees user_id and patient_id can never
        # disagree about whose document this is.
        user_id=patient.user_id,
        document_type=document_in.document_type,
        title=document_in.title,
        raw_text=document_in.raw_text,
        file_name=None,
        file_type=DEFAULT_FILE_TYPE,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def create_clinical_document_from_file(
    db: Session,
    patient: Patient,
    document_type: str,
    title: str,
    raw_text: str,
    file_name: str,
    file_type: str,
) -> ClinicalDocument:
    document = ClinicalDocument(
        patient_id=patient.id,
        user_id=patient.user_id,
        document_type=document_type,
        title=title,
        raw_text=raw_text,
        file_name=file_name,
        file_type=file_type,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def get_clinical_documents_for_patient(db: Session, patient_id: int) -> list[ClinicalDocument]:
    return (
        db.query(ClinicalDocument)
        .filter(ClinicalDocument.patient_id == patient_id)
        .order_by(ClinicalDocument.created_at.desc())
        .all()
    )


def get_clinical_document(
    db: Session, patient_id: int, document_id: int
) -> ClinicalDocument | None:
    return (
        db.query(ClinicalDocument)
        .filter(
            ClinicalDocument.id == document_id,
            ClinicalDocument.patient_id == patient_id,
        )
        .first()
    )


def delete_clinical_document(db: Session, patient_id: int, document_id: int) -> bool:
    document = get_clinical_document(db, patient_id, document_id)

    if document is None:
        return False

    db.delete(document)
    db.commit()

    return True
