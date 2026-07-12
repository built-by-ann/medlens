import csv
import io

from pydantic import ValidationError

from app.schemas.medication import MedicationCreate

REQUIRED_COLUMNS = ["medication_name", "dose", "route", "frequency", "status", "source"]
OPTIONAL_COLUMNS = ["notes"]
KNOWN_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


class CsvFormatError(Exception):
    pass


class CsvValidationError(Exception):
    def __init__(self, row_errors: list[dict]):
        self.row_errors = row_errors
        super().__init__("CSV import failed validation")


class MedicationCsvImportResult:
    def __init__(
        self,
        medications: list[MedicationCreate],
        rows_processed: int,
        blank_rows_ignored: int,
    ):
        self.medications = medications
        self.rows_processed = rows_processed
        self.blank_rows_ignored = blank_rows_ignored


def parse_medication_csv(decoded_text: str) -> MedicationCsvImportResult:
    if not decoded_text.strip():
        raise CsvFormatError("Uploaded file is empty")

    try:
        reader = csv.DictReader(io.StringIO(decoded_text))
        fieldnames = reader.fieldnames
        raw_rows = list(reader)
    except csv.Error:
        raise CsvFormatError("Could not parse CSV file")

    if not fieldnames:
        raise CsvFormatError("Uploaded file is empty")

    normalized_fieldnames = {(name or "").strip().lower() for name in fieldnames}

    missing_columns = [
        column for column in REQUIRED_COLUMNS if column not in normalized_fieldnames
    ]

    if missing_columns:
        raise CsvFormatError(
            "CSV is missing required column(s): " + ", ".join(missing_columns)
        )

    header_lookup = {(name or "").strip().lower(): name for name in fieldnames}

    rows_processed = 0
    blank_rows_ignored = 0
    row_errors = []
    validated_rows = []

    for line_number, raw_row in enumerate(raw_rows, start=2):
        rows_processed += 1

        cells = {}
        for column in KNOWN_COLUMNS:
            original_header = header_lookup.get(column)
            raw_value = raw_row.get(original_header, "") if original_header else ""
            cells[column] = (raw_value or "").strip()

        if all(value == "" for value in cells.values()):
            blank_rows_ignored += 1
            continue

        if cells.get("notes") == "":
            cells["notes"] = None

        try:
            validated_rows.append(MedicationCreate(**cells))
        except ValidationError as error:
            row_errors.append(
                {
                    "row": line_number,
                    "errors": [
                        {
                            "field": ".".join(str(part) for part in err["loc"]),
                            "message": err["msg"],
                        }
                        for err in error.errors()
                    ],
                }
            )

    if row_errors:
        raise CsvValidationError(row_errors)

    return MedicationCsvImportResult(
        medications=validated_rows,
        rows_processed=rows_processed,
        blank_rows_ignored=blank_rows_ignored,
    )
