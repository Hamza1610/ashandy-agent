"""Add checkpoints table for LangGraph conversation persistence

Revision ID: 002_add_checkpoints
Revises: 001_add_order_fields
Create Date: 2025-12-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = '002_add_checkpoints'
down_revision = '001_add_order_fields'
branch_labels = None
depends_on = None


def upgrade():
    """
    Create checkpoints table for LangGraph state persistence.
    
    This enables conversation history to be preserved across webhook calls.
    Each user gets a persistent "thread" identified by their phone number.
    """
    print("\n" + "="*80)
    print(">>> MIGRATION 002: Adding LangGraph Checkpoints Table")
    print("="*80 + "\n")
    
    print("[1/2] Creating checkpoints table...")
    
    op.create_table(
        'checkpoints',
        sa.Column('thread_id', sa.Text(), nullable=False, comment='User phone number or session ID'),
        sa.Column('checkpoint_ns', sa.Text(), nullable=False, server_default='', comment='Namespace for checkpoints'),
        sa.Column('checkpoint_id', sa.Text(), nullable=False, comment='Unique checkpoint identifier'),
        sa.Column('parent_checkpoint_id', sa.Text(), nullable=True, comment='Parent checkpoint for history'),
        sa.Column('type', sa.Text(), nullable=True, comment='Checkpoint type'),
        sa.Column('checkpoint', JSONB(), nullable=False, comment='Full state snapshot'),
        sa.Column('metadata', JSONB(), nullable=False, server_default='{}', comment='Additional metadata'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('thread_id', 'checkpoint_ns', 'checkpoint_id', name='checkpoints_pkey')
    )
    print("  [OK] checkpoints table created")
    
    print("\n[2/2] Creating indexes...")
    op.create_index(
        'checkpoints_thread_id_idx',
        'checkpoints',
        ['thread_id', 'checkpoint_ns'],
        unique=False
    )
    print("  [OK] checkpoints_thread_id_idx created")
    
    print("\n" + "="*80)
    print("[SUCCESS] MIGRATION 002 COMPLETED")
    print("="*80)
    print("Summary: Created checkpoints table + 1 index for conversation persistence")
    print("="*80 + "\n")


def downgrade():
    """
    Remove checkpoints table.
    """
    print("\n" + "="*80)
    print(">>> MIGRATION 002 ROLLBACK: Removing Checkpoints Table")
    print("="*80 + "\n")
    
    print("[1/2] Dropping indexes...")
    op.drop_index('checkpoints_thread_id_idx', table_name='checkpoints')
    print("  [OK] checkpoints_thread_id_idx dropped")
    
    print("\n[2/2] Dropping checkpoints table...")
    op.drop_table('checkpoints')
    print("  [OK] checkpoints table dropped")
    
    print("\n" + "="*80)
    print("[SUCCESS] MIGRATION 002 ROLLBACK COMPLETED")
    print("="*80 + "\n")
