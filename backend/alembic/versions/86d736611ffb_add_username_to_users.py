"""add username to users

Revision ID: 86d736611ffb
Revises: d9346397f3b5
Create Date: 2026-08-01 23:26:33.654024

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '86d736611ffb'
down_revision: Union[str, Sequence[str], None] = 'd9346397f3b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Purely additive: username is nullable, so every existing row is valid
    as-is with it left null; no backfill, no downgrade data loss for
    pre-existing users (Issue #191). Uniqueness is enforced case-
    insensitively via a functional unique index on lower(username) rather
    than a plain column-level unique constraint, which would be case-
    sensitive and let e.g. "jdoe" and "JDoe" coexist. NULLs are never equal
    to each other in a Postgres unique index, so any number of existing
    users can share a null username with no conflict.
    """
    op.add_column('users', sa.Column('username', sa.String(), nullable=True))
    op.create_index(
        'ix_users_username_lower',
        'users',
        [sa.text('lower(username)')],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema.

    Drops the index before the column it's defined over, the reverse
    order of upgrade(). Chosen usernames are lost, the same acceptable
    trade-off already established for other additive columns in this
    project (see e.g. d9346397f3b5's own downgrade).
    """
    op.drop_index('ix_users_username_lower', table_name='users')
    op.drop_column('users', 'username')
