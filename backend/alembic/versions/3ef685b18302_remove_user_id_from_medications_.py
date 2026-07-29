"""remove user_id from medications clinical_documents and analyses

Revision ID: 3ef685b18302
Revises: 599e0487bb6d
Create Date: 2026-07-29 12:32:34.392692

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ef685b18302'
down_revision: Union[str, Sequence[str], None] = '599e0487bb6d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ('medications', 'clinical_documents', 'analyses')


def upgrade() -> None:
    """Sprint 3.5, Issue #133: the final step of the Patient migration.

    Every row on all three tables has had a populated patient_id since the
    Issue #128 backfill, and every route/service has read patient_id (not
    user_id) for ownership since Issues #129/#130. user_id has been dead
    weight since then - this drops it, and tightens patient_id from
    nullable to NOT NULL now that it is the sole, always-populated
    ownership column. No data is lost: patient_id itself is untouched, and
    the dropped user_id values were never anything but a copy of
    `patient.user_id`, derivable again from patient_id alone (see
    downgrade()).
    """
    for table in _TABLES:
        op.drop_constraint(f'{table}_user_id_fkey', table, type_='foreignkey')
        op.drop_column(table, 'user_id')
        op.alter_column(table, 'patient_id', existing_type=sa.Integer(), nullable=False)


def downgrade() -> None:
    """Restores user_id by re-deriving it from patient_id (via
    `patients.user_id`), the same value it always held, rather than adding
    a NOT NULL column with nothing to populate it - Postgres would reject
    that outright on any table with existing rows. patient_id is loosened
    back to nullable only after user_id is fully repopulated, matching the
    schema's shape immediately before this migration's upgrade() ran.
    """
    connection = op.get_bind()

    for table in _TABLES:
        op.add_column(table, sa.Column('user_id', sa.Integer(), nullable=True))

        connection.execute(
            sa.text(
                f"""
                UPDATE {table}
                SET user_id = patients.user_id
                FROM patients
                WHERE {table}.patient_id = patients.id
                """
            )
        )

        op.alter_column(table, 'user_id', existing_type=sa.Integer(), nullable=False)
        op.create_foreign_key(f'{table}_user_id_fkey', table, 'users', ['user_id'], ['id'])
        op.alter_column(table, 'patient_id', existing_type=sa.Integer(), nullable=True)
