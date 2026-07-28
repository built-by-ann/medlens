"""add patient_id to medications clinical_documents and analyses

Revision ID: 599e0487bb6d
Revises: f4f1a2f9af04
Create Date: 2026-07-28 15:50:47.042200

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.services.patient_backfill_service import backfill_patient_ids, clear_patient_ids


# revision identifiers, used by Alembic.
revision: str = '599e0487bb6d'
down_revision: Union[str, Sequence[str], None] = 'f4f1a2f9af04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema, then backfill patient_id for every existing row.

    Both the schema change and the backfill run inside Alembic's own
    transaction (this project assumes transactional DDL - see alembic/
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

    session = Session(bind=op.get_bind())
    backfill_patient_ids(session)


def downgrade() -> None:
    """Nulls out patient_id everywhere, then drops the columns. See
    patient_backfill_service.clear_patient_ids for why this does not
    delete any placeholder Patient rows the backfill created.
    """
    session = Session(bind=op.get_bind())
    clear_patient_ids(session)

    op.drop_constraint('medications_patient_id_fkey', 'medications', type_='foreignkey')
    op.drop_index(op.f('ix_medications_patient_id'), table_name='medications')
    op.drop_column('medications', 'patient_id')
    op.drop_constraint('clinical_documents_patient_id_fkey', 'clinical_documents', type_='foreignkey')
    op.drop_index(op.f('ix_clinical_documents_patient_id'), table_name='clinical_documents')
    op.drop_column('clinical_documents', 'patient_id')
    op.drop_constraint('analyses_patient_id_fkey', 'analyses', type_='foreignkey')
    op.drop_index(op.f('ix_analyses_patient_id'), table_name='analyses')
    op.drop_column('analyses', 'patient_id')
