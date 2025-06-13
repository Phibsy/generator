# alembic/versions/xxxx_add_asset_management_tables.py
"""Add asset management tables

Revision ID: xxxx
Revises: yyyy
Create Date: 2025-01-13 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = 'xxxx'
down_revision = 'yyyy'
branch_labels = None
depends_on = None

def upgrade():
    # Create asset type enum
    asset_type_enum = postgresql.ENUM(
        'background_video', 'music', 'sound_effect', 'image', 'font', 'template',
        name='assettype'
    )
    asset_type_enum.create(op.get_bind())
    
    # Create other enums
    asset_status_enum = postgresql.ENUM(
        'processing', 'active', 'archived', 'failed',
        name='assetstatus'
    )
    asset_status_enum.create(op.get_bind())
    
    license_type_enum = postgresql.ENUM(
        'royalty_free', 'creative_commons', 'purchased', 'custom', 'public_domain',
        name='licensetype'
    )
    license_type_enum.create(op.get_bind())
    
    content_rating_enum = postgresql.ENUM(
        'general', 'teen', 'mature',
        name='contentrating'
    )
    content_rating_enum.create(op.get_bind())
    
    # Create assets table
    op.create_table(
        'assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('asset_type', asset_type_enum, nullable=False),
        sa.Column('status', asset_status_enum, nullable=True),
        sa.Column('file_path', sa.String(500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('file_format', sa.String(50), nullable=True),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('resolution', sa.String(50), nullable=True),
        sa.Column('cdn_url', sa.String(500), nullable=True),
        sa.Column('thumbnail_url', sa.String(500), nullable=True),
        sa.Column('preview_url', sa.String(500), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('categories', sa.JSON(), nullable=True),
        sa.Column('content_rating', content_rating_enum, nullable=True),
        sa.Column('energy_level', sa.Float(), nullable=True),
        sa.Column('tempo', sa.Integer(), nullable=True),
        sa.Column('dominant_colors', sa.JSON(), nullable=True),
        sa.Column('license_type', license_type_enum, nullable=False),
        sa.Column('license_details', sa.JSON(), nullable=True),
        sa.Column('attribution_required', sa.Boolean(), nullable=True),
        sa.Column('attribution_text', sa.Text(), nullable=True),
        sa.Column('usage_count', sa.Integer(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('popularity_score', sa.Float(), nullable=True),
        sa.Column('source_url', sa.String(500), nullable=True),
        sa.Column('source_attribution', sa.String(500), nullable=True),
        sa.Column('uploaded_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_assets_asset_id'), 'assets', ['asset_id'], unique=True)
    op.create_index('idx_asset_type_status', 'assets', ['asset_type', 'status'])
    op.create_index('idx_asset_tags', 'assets', ['tags'], postgresql_using='gin')
    
    # Create other tables
    op.create_table(
        'asset_collections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('collection_type', sa.String(50), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=True),
        sa.Column('is_featured', sa.Boolean(), nullable=True),
        sa.Column('is_public', sa.Boolean(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table(
        'collection_assets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('collection_id', sa.Integer(), nullable=True),
        sa.Column('asset_id', sa.Integer(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
        sa.ForeignKeyConstraint(['collection_id'], ['asset_collections.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table(
        'asset_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('project_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('usage_type', sa.String(50), nullable=True),
        sa.Column('usage_duration', sa.Float(), nullable=True),
        sa.Column('usage_context', sa.JSON(), nullable=True),
        sa.Column('used_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_usage_asset_project', 'asset_usage', ['asset_id', 'project_id'])
    
    op.create_table(
        'copyright_reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('asset_id', sa.Integer(), nullable=False),
        sa.Column('reported_by', sa.Integer(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('evidence_url', sa.String(500), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('resolution', sa.Text(), nullable=True),
        sa.Column('reported_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ),
        sa.ForeignKeyConstraint(['reported_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    op.drop_table('copyright_reports')
    op.drop_table('asset_usage')
    op.drop_table('collection_assets')
    op.drop_table('asset_collections')
    op.drop_table('assets')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS contentrating')
    op.execute('DROP TYPE IF EXISTS licensetype')
    op.execute('DROP TYPE IF EXISTS assetstatus')
    op.execute('DROP TYPE IF EXISTS assettype')
