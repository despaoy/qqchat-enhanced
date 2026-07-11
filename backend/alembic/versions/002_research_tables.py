"""研究与评估相关表（LLM Research Enhancement Roadmap）

Revision ID: 002_research
Revises: 001_initial
Create Date: 2026-07-11 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '002_research'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'gold_eval_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_at', sa.String(), nullable=False),
        sa.Column('adapter_name', sa.String(), nullable=True),
        sa.Column('model_label', sa.String(), nullable=True),
        sa.Column('total_prompts', sa.Integer(), server_default='0'),
        sa.Column('category_breakdown', sa.Text(), nullable=True),
        sa.Column('metrics', sa.Text(), nullable=True),
        sa.Column('config_snapshot', sa.Text(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'experiment_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('experiment_type', sa.String(), nullable=False),
        sa.Column('hypothesis', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('started_at', sa.String(), nullable=False),
        sa.Column('completed_at', sa.String(), nullable=True),
        sa.Column('results', sa.Text(), nullable=True),
        sa.Column('config_path', sa.String(), nullable=True),
        sa.Column('report_path', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'retrieval_eval_questions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('question', sa.Text(), nullable=False),
        sa.Column('expected_doc_ids', sa.Text(), nullable=True),
        sa.Column('expected_doc_titles', sa.Text(), nullable=True),
        sa.Column('gold_answer', sa.Text(), nullable=True),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'preference_pairs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('chosen', sa.Text(), nullable=False),
        sa.Column('rejected', sa.Text(), nullable=False),
        sa.Column('rubric', sa.Text(), nullable=True),
        sa.Column('annotator', sa.String(), nullable=True),
        sa.Column('metadata', sa.Text(), nullable=True),
        sa.Column('review_status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'adapter_compatibility',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('adapter_name', sa.String(), nullable=False),
        sa.Column('checked_at', sa.String(), nullable=False),
        sa.Column('compatible', sa.Integer(), nullable=False),
        sa.Column('checks', sa.Text(), nullable=True),
        sa.Column('warnings', sa.Text(), nullable=True),
        sa.Column('errors', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'feedback',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('trace_id', sa.String(), nullable=True),
        sa.Column('message_id', sa.String(), nullable=True),
        sa.Column('rating', sa.String(), nullable=True),
        sa.Column('reason', sa.String(), nullable=True),
        sa.Column('adapter_name', sa.String(), nullable=True),
        sa.Column('kb_revision', sa.String(), nullable=True),
        sa.Column('prompt_version', sa.String(), nullable=True),
        sa.Column('detail', sa.Text(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index('idx_experiment_runs_type', 'experiment_runs', ['experiment_type'])
    op.create_index('idx_preference_pairs_status', 'preference_pairs', ['review_status'])
    op.create_index('idx_feedback_created', 'feedback', ['created_at'])
    op.create_index('idx_adapter_compat_name', 'adapter_compatibility', ['adapter_name'])


def downgrade() -> None:
    op.drop_index('idx_adapter_compat_name', table_name='adapter_compatibility')
    op.drop_index('idx_feedback_created', table_name='feedback')
    op.drop_index('idx_preference_pairs_status', table_name='preference_pairs')
    op.drop_index('idx_experiment_runs_type', table_name='experiment_runs')
    op.drop_table('feedback')
    op.drop_table('adapter_compatibility')
    op.drop_table('preference_pairs')
    op.drop_table('retrieval_eval_questions')
    op.drop_table('experiment_runs')
    op.drop_table('gold_eval_runs')
