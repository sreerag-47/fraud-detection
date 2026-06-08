"""merge_branches_and_add_geo_velocity_rule

Revision ID: a3d6a20339d4
Revises: 1c94f18bcef4, c3d4e5f6a7b8
Create Date: 2026-06-08 12:35:48.843574

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3d6a20339d4'
down_revision: Union[str, Sequence[str], None] = ('1c94f18bcef4', 'c3d4e5f6a7b8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Clean up triggers created by trigger-based head
    op.execute("DROP TRIGGER IF EXISTS trg_transactions_fraud_actions ON transactions CASCADE;")
    op.execute("DROP TRIGGER IF EXISTS trg_transactions_fraud_check ON transactions CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS process_transaction_fraud_actions() CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS process_transaction_fraud_check() CASCADE;")

    # 2. Insert GEO-VEL-01 dynamic rule
    op.execute(sa.text(r"""
    INSERT INTO fraud_rules (code, name, description, sql_expression, weight, is_active)
    VALUES
    ('GEO-VEL-01', 'Rapid Geo-Jump', 'Rapid different country transaction within 15 minutes',
     'SELECT EXISTS (SELECT 1 FROM transactions WHERE account_id = \:account_id AND country <> \:country AND timestamp >= NOW() - INTERVAL ''15 minutes'')', 0.50, true);
    """))


def downgrade() -> None:
    # Remove GEO-VEL-01 dynamic rule
    op.execute(sa.text("DELETE FROM fraud_rules WHERE code = 'GEO-VEL-01';"))
