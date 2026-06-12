"""初始数据库模式

Revision ID: 001_initial
Revises: None
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 用户表
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('created_at', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # 配置表
    op.create_table(
        'config',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('key'),
    )

    # 消息表
    op.create_table(
        'messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(), nullable=True),
        sa.Column('session_type', sa.String(), nullable=True),
        sa.Column('user_message', sa.String(), nullable=True),
        sa.Column('bot_reply', sa.String(), nullable=True),
        sa.Column('lora_name', sa.String(), nullable=True),
        sa.Column('timestamp', sa.String(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # LoRA模型表
    op.create_table(
        'loras',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False, unique=True),
        sa.Column('path', sa.String(), nullable=True),
        sa.Column('active', sa.Integer(), nullable=True, default=0),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # 知识库表
    op.create_table(
        'knowledge_bases',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=True),
        sa.Column('updated_at', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # 知识库文件夹表
    op.create_table(
        'knowledge_folders',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('kbId', sa.Integer(), nullable=True),
        sa.Column('parentId', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=True),
        sa.Column('updated_at', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # 知识库文档表
    op.create_table(
        'knowledge_documents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('title', sa.String(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('summary', sa.String(), nullable=True),
        sa.Column('folderId', sa.Integer(), nullable=True),
        sa.Column('kbId', sa.Integer(), nullable=True),
        sa.Column('chunkCount', sa.Integer(), nullable=True, default=0),
        sa.Column('charCount', sa.Integer(), nullable=True, default=0),
        sa.Column('status', sa.String(), nullable=True, default='active'),
        sa.Column('tags', sa.String(), nullable=True),
        sa.Column('source', sa.String(), nullable=True),
        sa.Column('category', sa.String(), nullable=True, default='未分类'),
        sa.Column('createdAt', sa.String(), nullable=True),
        sa.Column('updatedAt', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # 知识库文档分块表
    op.create_table(
        'knowledge_chunks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # 用户数据持久化表
    op.create_table(
        'user_data',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('page_key', sa.String(), nullable=False),
        sa.Column('data', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username', 'page_key'),
    )

    # 审计日志表
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('timestamp', sa.String(), nullable=True),
        sa.Column('client_ip', sa.String(), nullable=True),
        sa.Column('user', sa.String(), nullable=True),
        sa.Column('path', sa.String(), nullable=True),
        sa.Column('method', sa.String(), nullable=True),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('audit_logs')
    op.drop_table('user_data')
    op.drop_table('knowledge_chunks')
    op.drop_table('knowledge_documents')
    op.drop_table('knowledge_folders')
    op.drop_table('knowledge_bases')
    op.drop_table('loras')
    op.drop_table('messages')
    op.drop_table('config')
    op.drop_table('users')
