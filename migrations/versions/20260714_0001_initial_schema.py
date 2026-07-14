"""Initial TradePilot scaffold schema.

Revision ID: 20260714_0001
Revises:
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260714_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("data_mode", sa.String(length=16), nullable=False),
        sa.Column("data_origin", sa.String(length=16), nullable=False),
        sa.Column("attributes_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("product_id"),
    )
    op.create_index("ix_products_data_origin", "products", ["data_origin"])
    op.create_table(
        "product_files",
        sa.Column("file_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.PrimaryKeyConstraint("file_id"),
    )
    op.create_index("ix_product_files_product_id", "product_files", ["product_id"])
    op.create_table(
        "competitor_offers",
        sa.Column("offer_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("data_origin", sa.String(length=16), nullable=False),
        sa.Column("attributes_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.PrimaryKeyConstraint("offer_id"),
    )
    op.create_index("ix_competitor_offers_data_origin", "competitor_offers", ["data_origin"])
    op.create_index("ix_competitor_offers_product_id", "competitor_offers", ["product_id"])
    op.create_table(
        "reviews",
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("data_origin", sa.String(length=16), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.PrimaryKeyConstraint("review_id"),
    )
    op.create_index("ix_reviews_data_origin", "reviews", ["data_origin"])
    op.create_index("ix_reviews_product_id", "reviews", ["product_id"])
    op.create_table(
        "knowledge_sources",
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=True),
        sa.Column("knowledge_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("data_origin", sa.String(length=16), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_index("ix_knowledge_sources_data_origin", "knowledge_sources", ["data_origin"])
    op.create_index("ix_knowledge_sources_knowledge_type", "knowledge_sources", ["knowledge_type"])
    op.create_index("ix_knowledge_sources_product_id", "knowledge_sources", ["product_id"])
    op.create_table(
        "analysis_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=False),
        sa.Column("data_mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("current_node", sa.String(length=64), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.String(length=36), nullable=True),
        sa.Column("request_json", sa.JSON(), nullable=False),
        sa.Column("state_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_analysis_runs_product_id", "analysis_runs", ["product_id"])
    op.create_index("ix_analysis_runs_status", "analysis_runs", ["status"])
    op.create_table(
        "agent_outputs",
        sa.Column("output_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("input_json", sa.JSON(), nullable=False),
        sa.Column("output_json", sa.JSON(), nullable=False),
        sa.Column("error_json", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.run_id"]),
        sa.PrimaryKeyConstraint("output_id"),
    )
    op.create_index("ix_agent_outputs_agent_name", "agent_outputs", ["agent_name"])
    op.create_index("ix_agent_outputs_run_id", "agent_outputs", ["run_id"])
    op.create_table(
        "evidence_references",
        sa.Column("record_id", sa.String(length=36), nullable=False),
        sa.Column("evidence_id", sa.String(length=128), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_type", sa.String(length=32), nullable=False),
        sa.Column("data_origin", sa.String(length=16), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.run_id"]),
        sa.PrimaryKeyConstraint("record_id"),
    )
    op.create_index("ix_evidence_references_data_origin", "evidence_references", ["data_origin"])
    op.create_index("ix_evidence_references_evidence_id", "evidence_references", ["evidence_id"])
    op.create_index("ix_evidence_references_run_id", "evidence_references", ["run_id"])
    op.create_table(
        "reports",
        sa.Column("report_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("is_demo", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["analysis_runs.run_id"]),
        sa.PrimaryKeyConstraint("report_id"),
    )
    op.create_index("ix_reports_run_id", "reports", ["run_id"])
    op.create_table(
        "conversations",
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("product_id", sa.String(length=36), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.product_id"]),
        sa.PrimaryKeyConstraint("conversation_id"),
    )
    op.create_table(
        "messages",
        sa.Column("message_id", sa.String(length=36), nullable=False),
        sa.Column("conversation_id", sa.String(length=36), nullable=False),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.conversation_id"]),
        sa.PrimaryKeyConstraint("message_id"),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])


def downgrade() -> None:
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_index("ix_reports_run_id", table_name="reports")
    op.drop_table("reports")
    op.drop_index("ix_evidence_references_run_id", table_name="evidence_references")
    op.drop_index("ix_evidence_references_evidence_id", table_name="evidence_references")
    op.drop_index("ix_evidence_references_data_origin", table_name="evidence_references")
    op.drop_table("evidence_references")
    op.drop_index("ix_agent_outputs_run_id", table_name="agent_outputs")
    op.drop_index("ix_agent_outputs_agent_name", table_name="agent_outputs")
    op.drop_table("agent_outputs")
    op.drop_index("ix_analysis_runs_status", table_name="analysis_runs")
    op.drop_index("ix_analysis_runs_product_id", table_name="analysis_runs")
    op.drop_table("analysis_runs")
    op.drop_index("ix_knowledge_sources_product_id", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_knowledge_type", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_data_origin", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")
    op.drop_index("ix_reviews_product_id", table_name="reviews")
    op.drop_index("ix_reviews_data_origin", table_name="reviews")
    op.drop_table("reviews")
    op.drop_index("ix_competitor_offers_product_id", table_name="competitor_offers")
    op.drop_index("ix_competitor_offers_data_origin", table_name="competitor_offers")
    op.drop_table("competitor_offers")
    op.drop_index("ix_product_files_product_id", table_name="product_files")
    op.drop_table("product_files")
    op.drop_index("ix_products_data_origin", table_name="products")
    op.drop_table("products")
