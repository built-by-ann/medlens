from sqlalchemy.orm import Session, selectinload

from app.models.clinical_document import ClinicalDocument
from app.models.patient import Patient
from app.schemas.clinical_document import ClinicalDocumentCreate

DEFAULT_FILE_TYPE = "manual_entry"
TXT_FILE_TYPE = "txt"
PDF_FILE_TYPE = "pdf"
CSV_FILE_TYPE = "csv"


def create_clinical_document(
    db: Session, patient: Patient, document_in: ClinicalDocumentCreate
) -> ClinicalDocument:
    document = ClinicalDocument(
        patient_id=patient.id,
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
    # selectinload avoids an N+1 query for analysis_count (Issue #146),
    # which reads the analyses relationship on every returned document.
    return (
        db.query(ClinicalDocument)
        .options(selectinload(ClinicalDocument.analyses))
        .filter(ClinicalDocument.patient_id == patient_id)
        .order_by(ClinicalDocument.created_at.desc())
        .all()
    )


def get_clinical_document(
    db: Session, patient_id: int, document_id: int
) -> ClinicalDocument | None:
    return (
        db.query(ClinicalDocument)
        .options(selectinload(ClinicalDocument.analyses))
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
