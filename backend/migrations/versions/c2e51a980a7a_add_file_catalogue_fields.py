"""add stable file catalogue fields

Revision ID: c2e51a980a7a
Revises: b77ac003de42
Create Date: 2026-10-16
"""
from alembic import op
import sqlalchemy as sa

revision = "c2e51a980a7a"
down_revision = "b77ac003de42"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("products", sa.Column("digital_product_id", sa.String(length=120), nullable=True))
    op.add_column("products", sa.Column("s_no", sa.Integer(), nullable=True))
    op.create_index("ix_products_digital_product_id", "products", ["digital_product_id"], unique=True)
    op.create_index("ix_products_s_no", "products", ["s_no"], unique=False)


def downgrade():
    op.drop_index("ix_products_s_no", table_name="products")
    op.drop_index("ix_products_digital_product_id", table_name="products")
    op.drop_column("products", "s_no")
    op.drop_column("products", "digital_product_id")
