"""add patient_id to medications clinical_documents and analyses

Revision ID: 599e0487bb6d
Revises: f4f1a2f9af04
Create Date: 2026-07-28 15:50:47.042200

"""
from datetime import date
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '599e0487bb6d'
down_revision: Union[str, Sequence[str], None] = 'f4f1a2f9af04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# --- Frozen backfill logic ------------------------------------------------
#
# This used to import backfill_patient_ids/clear_patient_ids from
# app.services.patient_backfill_service, which operated on the live ORM
# models (Medication, ClinicalDocument, Analysis, Patient, User). Sprint 3.5,
# Issue #133 removed user_id from those three models entirely, the exact
# "later renamed or restructured" risk patient_backfill_service.py's own
# docstring warned about. A historical migration must keep working when
# replayed from scratch against an empty database, which means it can never
# depend on today's model shape; importing the live models would make
# upgrade() here crash the moment Medication.user_id stopped existing, even
# though this step in history is exactly when that column still existed.
#
# The fix is the standard Alembic pattern: this migration now speaks only to
# lightweight, local `sa.table()` shadows scoped to the columns this step
# actually touches, frozen at this point in schema history, not to the
# current application models. See the plain SQL swapped in below for
# `backfill_patient_ids`/`clear_patient_ids`'s original logic; the service
# module itself and its tests were removed in Issue #133 since nothing else
# ever called them.

ACTIVE_STATUS = "active"
LEGACY_PATIENT_FIRST_NAME = "Legacy"
LEGACY_PATIENT_LAST_NAME = "Patient"
LEGACY_PATIENT_DATE_OF_BIRTH = date(1900, 1, 1)
LEGACY_PATIENT_NOTES = "Automatically created during patient migration."

_users = sa.table("users", sa.column("id", sa.Integer))
_patients = sa.table(
    "patients",
    sa.column("id", sa.Integer),
    sa.column("user_id", sa.Integer),
    sa.column("first_name", sa.String),
    sa.column("last_name", sa.String),
    sa.column("date_of_birth", sa.Date),
    sa.column("external_mrn", sa.String),
    sa.column("status", sa.String),
    sa.column("notes", sa.Text),
)
_legacy_tables = [
    sa.table(
        name,
        sa.column("id", sa.Integer),
        sa.column("user_id", sa.Integer),
        sa.column("patient_id", sa.Integer),
    )
    for name in ("medications", "clinical_documents", "analyses")
]


class AmbiguousPatientBackfillError(Exception):
    def __init__(self, user_id: int, active_patient_ids: list[int]):
        super().__init__(
            f"Cannot backfill patient_id for user {user_id}: {len(active_patient_ids)} "
            f"active patients exist ({active_patient_ids}) and this user has legacy "
            "medications, clinical documents, or analyses that need a patient assigned. "
            "Refusing to guess which patient owns them - resolve manually (archive the "
            "extra patients, or set patient_id by hand for this user's legacy records) "
            "and re-run this migration."
        )


def _backfill_patient_ids(connection) -> None:
    user_ids = [row.id for row in connection.execute(sa.select(_users.c.id).order_by(_users.c.id))]

    for user_id in user_ids:
        legacy_rows_by_table = {
            table: connection.execute(
                sa.select(table.c.id).where(
                    table.c.user_id == user_id, table.c.patient_id.is_(None)
                )
            ).fetchall()
            for table in _legacy_tables
        }

        if not any(legacy_rows_by_table.values()):
            continue

        active_patient_ids = [
            row.id
            for row in connection.execute(
                sa.select(_patients.c.id)
                .where(_patients.c.user_id == user_id, _patients.c.status == ACTIVE_STATUS)
                .order_by(_patients.c.id)
            )
        ]

        if len(active_patient_ids) > 1:
            raise AmbiguousPatientBackfillError(user_id, active_patient_ids)

        if active_patient_ids:
            target_patient_id = active_patient_ids[0]
        else:
            result = connection.execute(
                sa.insert(_patients).values(
                    user_id=user_id,
                    first_name=LEGACY_PATIENT_FIRST_NAME,
                    last_name=LEGACY_PATIENT_LAST_NAME,
                    date_of_birth=LEGACY_PATIENT_DATE_OF_BIRTH,
                    external_mrn=None,
                    status=ACTIVE_STATUS,
                    notes=LEGACY_PATIENT_NOTES,
                )
            )
            target_patient_id = result.inserted_primary_key[0]

        for table, rows in legacy_rows_by_table.items():
            if not rows:
                continue

            row_ids = [row.id for row in rows]
            connection.execute(
                sa.update(table).where(table.c.id.in_(row_ids)).values(patient_id=target_patient_id)
            )

    for table in _legacy_tables:
        orphan_count = connection.execute(
            sa.select(sa.func.count()).select_from(table).where(table.c.patient_id.is_(None))
        ).scalar_one()

        if orphan_count:
            raise RuntimeError(
                f"{orphan_count} {table.name} row(s) still have no patient_id after "
                "backfill - this indicates a bug in the backfill logic itself."
            )


def _clear_patient_ids(connection) -> None:
    for table in _legacy_tables:
        connection.execute(sa.update(table).values(patient_id=None))


# --- End frozen backfill logic --------------------------------------------


def upgrade() -> None:
    """Upgrade schema, then backfill patient_id for every existing row.

    Both the schema change and the backfill run inside Alembic's own
    transaction (this project assumes transactional DDL; see alembic/
    env.py), so a failure partway through the backfill (an ambiguous
    multi-patient user) rolls back the ALTER TABLE statements too, leaving
    the database exactly as it was before this migration ran.
    """
    op.add_column('analyses', sa.Column('patient_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_analyses_patient_id'), 'analyses', ['patient_id'], unique=False)
    op.create_foreign_key(
        'analyses_patient_id_fkey', 'analyses', 'patients', ['patient_id'], ['id']
    )
    op.add_column('clinical_documents', sa.Column('patient_id', sa.Integer(), nullable=True))
    op.create_index(
        op.f('ix_clinical_documents_patient_id'), 'clinical_documents', ['patient_id'], unique=False
    )
    op.create_foreign_key(
        'clinical_documents_patient_id_fkey',
        'clinical_documents',
        'patients',
        ['patient_id'],
        ['id'],
    )
    op.add_column('medications', sa.Column('patient_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_medications_patient_id'), 'medications', ['patient_id'], unique=False)
    op.create_foreign_key(
        'medications_patient_id_fkey', 'medications', 'patients', ['patient_id'], ['id']
    )

    _backfill_patient_ids(op.get_bind())


def downgrade() -> None:
    """Nulls out patient_id everywhere, then drops the columns. Does not
    delete any placeholder Patient rows the backfill created; by the time
    this runs they are ordinary, real Patient rows (editable through the
    Patient API), and deleting them is a much riskier, less reversible
    operation than simply unsetting a foreign key.
    """
    _clear_patient_ids(op.get_bind())

    op.drop_constraint('medications_patient_id_fkey', 'medications', type_='foreignkey')
    op.drop_index(op.f('ix_medications_patient_id'), table_name='medications')
    op.drop_column('medications', 'patient_id')
    op.drop_constraint('clinical_documents_patient_id_fkey', 'clinical_documents', type_='foreignkey')
    op.drop_index(op.f('ix_clinical_documents_patient_id'), table_name='clinical_documents')
    op.drop_column('clinical_documents', 'patient_id')
    op.drop_constraint('analyses_patient_id_fkey', 'analyses', type_='foreignkey')
    op.drop_index(op.f('ix_analyses_patient_id'), table_name='analyses')
    op.drop_column('analyses', 'patient_id')
