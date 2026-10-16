"""Add product storage and price checks.

Revision ID: b77ac003de42
Revises: 990ce49cdf29
"""
from alembic import op


revision = "b77ac003de42"
down_revision = "990ce49cdf29"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("products") as batch:
        batch.create_check_constraint("ck_products_price_nonnegative", "price >= 0")
    with op.batch_alter_table("product_resources") as batch:
        batch.create_check_constraint("ck_product_resources_type", "resource_type IN ('file', 'canva_url')")
        batch.create_check_constraint("ck_product_resources_location", "(resource_type = 'file' AND private_storage_key IS NOT NULL) OR (resource_type = 'canva_url' AND external_url IS NOT NULL)")


def downgrade():
    with op.batch_alter_table("product_resources") as batch:
        batch.drop_constraint("ck_product_resources_location", type_="check")
        batch.drop_constraint("ck_product_resources_type", type_="check")
    with op.batch_alter_table("products") as batch:
        batch.drop_constraint("ck_products_price_nonnegative", type_="check")
