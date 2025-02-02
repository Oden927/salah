"""Ajout de phase_duration ou des durées spécifiques par phase

Revision ID: 95fe3e71be4e
Revises: 7f98d5ef3bf5
Create Date: 2025-01-04 22:54:39.322205

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '95fe3e71be4e'
down_revision = '7f98d5ef3bf5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('game', schema=None) as batch_op:
        batch_op.add_column(sa.Column('phase_duration', sa.Integer(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('game', schema=None) as batch_op:
        batch_op.drop_column('phase_duration')

    # ### end Alembic commands ###
