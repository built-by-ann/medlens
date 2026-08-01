from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_owned_patient
from app.db.session import get_db
from app.models.patient import Patient
from app.schemas.medication import (
    MedicationCreate,
    MedicationImportSummary,
    MedicationResponse,
    MedicationUpdate,
)
from app.services.medication_import_service import (
    CsvFormatError,
    CsvValidationError,
    parse_medication_csv,
)
from app.services.medication_service import (
    create_medication,
    create_medications_from_rows,
    delete_medication,
    get_medication,
    get_medications_for_patient,
    update_medication,
)

router = APIRouter(prefix="/patients/{patient_id}/medications", tags=["medications"])

NOT_FOUND_DETAIL = "Medication not found"


@router.post(
    "",
    response_model=MedicationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_medication_route(
    medication_in: MedicationCreate,
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> MedicationResponse:
    return create_medication(db, patient, medication_in)


@router.post(
    "/import",
    response_model=MedicationImportSummary,
    status_code=status.HTTP_201_CREATED,
)
def import_medications(
    file: UploadFile = File(...),
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> MedicationImportSummary:
    is_csv_extension = (file.filename or "").lower().endswith(".csv")
    is_csv_content_type = file.content_type == "text/csv"

    if not (is_csv_extension or is_csv_content_type):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only .csv or text/csv files are supported",
        )

    contents = file.file.read()

    try:
        decoded_text = contents.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File must be valid UTF-8 encoded text",
        ) from None

    try:
        result = parse_medication_csv(decoded_text)
    except CsvFormatError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(error),
        ) from None
    except CsvValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "message": "CSV import failed validation. No medications were created.",
                "row_errors": error.row_errors,
            },
        ) from None

    medications_created = create_medications_from_rows(db, patient, result.medications)

    return MedicationImportSummary(
        rows_processed=result.rows_processed,
        medications_created=medications_created,
        blank_rows_ignored=result.blank_rows_ignored,
    )


@router.get("", response_model=list[MedicationResponse])
def list_medications(
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> list[MedicationResponse]:
    return get_medications_for_patient(db, patient.id)


@router.get("/{medication_id}", response_model=MedicationResponse)
def read_medication(
    medication_id: int,
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> MedicationResponse:
    medication = get_medication(db, patient.id, medication_id)

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
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> MedicationResponse:
    medication = update_medication(db, patient.id, medication_id, medication_in)

    if medication is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )

    return medication


@router.delete("/{medication_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_medication(
    medication_id: int,
    patient: Patient = Depends(get_owned_patient),
    db: Session = Depends(get_db),
) -> None:
    deleted = delete_medication(db, patient.id, medication_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=NOT_FOUND_DETAIL,
        )
