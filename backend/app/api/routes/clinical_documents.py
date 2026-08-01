from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_owned_patient
from app.core.pdf import PdfExtractionError, extract_text_from_pdf
from app.db.session import get_db
from app.models.patient import Patient
from app.schemas.clinical_document import ClinicalDocumentCreate, ClinicalDocumentResponse
from app.services.clinical_document_service import (
    CSV_FILE_TYPE,
    PDF_FILE_TYPE,
    TXT_FILE_TYPE,
    create_clinical_document,
    create_clinical_document_from_file,
    delete_clinical_document,
    get_clinical_document,
    get_clinical_documents_for_patient,
)

router = APIRouter(prefix="/patients/{patient_id}/clinical-documents", tags=["clinical-documents"])

NOT_FOUND_DETAIL = "Clinical document not found"


@router.post(
    "",
    response_model=ClinicalDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    document_in: ClinicalDocumentCreate,
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> ClinicalDocumentResponse:
    return create_clinical_document(db, patient, document_in)


@router.post(
    "/upload-txt",
    response_model=ClinicalDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_txt_document(
    document_type: str = Form(min_length=1),
    title: str = Form(min_length=1),
    file: UploadFile = File(...),
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> ClinicalDocumentResponse:
    is_txt_extension = (file.filename or "").lower().endswith(".txt")
    is_plain_text_content_type = file.content_type == "text/plain"

    if not (is_txt_extension or is_plain_text_content_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only .txt or text/plain files are supported",
        )

    contents = file.file.read()

    try:
        raw_text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File must be valid UTF-8 encoded text",
        ) from None

    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded file is empty",
        )

    return create_clinical_document_from_file(
        db,
        patient,
        document_type=document_type,
        title=title,
        raw_text=raw_text,
        file_name=file.filename,
        file_type=TXT_FILE_TYPE,
    )


@router.post(
    "/upload-pdf",
    response_model=ClinicalDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_pdf_document(
    document_type: str = Form(min_length=1),
    title: str = Form(min_length=1),
    file: UploadFile = File(...),
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> ClinicalDocumentResponse:
    is_pdf_extension = (file.filename or "").lower().endswith(".pdf")
    is_pdf_content_type = file.content_type == "application/pdf"

    if not (is_pdf_extension or is_pdf_content_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only .pdf or application/pdf files are supported",
        )

    contents = file.file.read()

    if not contents:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded file is empty",
        )

    try:
        raw_text = extract_text_from_pdf(contents)
    except PdfExtractionError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File must be a valid PDF",
        ) from None

    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No extractable text found in PDF",
        )

    return create_clinical_document_from_file(
        db,
        patient,
        document_type=document_type,
        title=title,
        raw_text=raw_text,
        file_name=file.filename,
        file_type=PDF_FILE_TYPE,
    )


@router.post(
    "/upload-csv",
    response_model=ClinicalDocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_csv_document(
    document_type: str = Form(min_length=1),
    title: str = Form(min_length=1),
    file: UploadFile = File(...),
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> ClinicalDocumentResponse:
    # Issue #164: a CSV uploaded here becomes an ordinary clinical document -
    # evidence for AI extraction and reconciliation - not a medication
    # import. Deliberately does not call parse_medication_csv /
    # create_medications_from_rows (app/services/medication_import_service.py,
    # the /patients/{id}/medications/import route in medications.py); the raw
    # CSV text is stored and flows through the exact same pipeline as an
    # uploaded .txt file, with nothing patient-medication-specific about it.
    is_csv_extension = (file.filename or "").lower().endswith(".csv")
    is_csv_content_type = file.content_type == "text/csv"

    if not (is_csv_extension or is_csv_content_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only .csv or text/csv files are supported",
        )

    contents = file.file.read()

    try:
        raw_text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File must be valid UTF-8 encoded text",
        ) from None

    if not raw_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Uploaded file is empty",
        )

    return create_clinical_document_from_file(
        db,
        patient,
        document_type=document_type,
        title=title,
        raw_text=raw_text,
        file_name=file.filename,
        file_type=CSV_FILE_TYPE,
    )


@router.get("", response_model=list[ClinicalDocumentResponse])
def list_documents(
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> list[ClinicalDocumentResponse]:
    return get_clinical_documents_for_patient(db, patient.id)


@router.get("/{document_id}", response_model=ClinicalDocumentResponse)
def read_document(
    document_id: int,
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> ClinicalDocumentResponse:
    document = get_clinical_document(db, patient.id, document_id)

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )

    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    document_id: int,
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> None:
    deleted = delete_clinical_document(db, patient.id, document_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )
