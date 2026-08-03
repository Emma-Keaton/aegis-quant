"""Alembic migration: create all tables for Aegis Quant."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '007_add_auth_and_copytrade'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # profiles table
    op.create_table(
        'profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('telegram_id', sa.BigInteger, unique=True, nullable=False, index=True),
        sa.Column('username', sa.String(100), nullable=True),
        sa.Column('first_name', sa.String(100), nullable=True),
        sa.Column('last_name', sa.String(100), nullable=True),
        sa.Column('language_code', sa.String(10), nullable=True),
        sa.Column('wallet_connected', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('wallet_address', sa.String(64), nullable=True),
        sa.Column('wallet_network', sa.String(10), nullable=True),
        sa.Column('wallet_public_key', sa.String(128), nullable=True),
        sa.Column('engine_b_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('engine_b_min_confidence', sa.Numeric(3, 2), server_default='0.70', nullable=False),
        sa.Column('risk_level', sa.String(20), server_default='medium', nullable=False),
        sa.Column('max_allocation_pct', sa.Numeric(5, 2), server_default='10.0', nullable=False),
        sa.Column('max_concurrent_trades', sa.Integer, server_default='3', nullable=False),
        sa.Column('trading_mode', sa.String(20), server_default='paper', nullable=False),
        sa.Column('bot_enabled', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('engine_a_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # user_sessions table
    op.create_table(
        'user_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('telegram_id', sa.BigInteger, nullable=False, index=True),
        sa.Column('profile_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('token', sa.String(512), unique=True, nullable=False, index=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # copytrade_channels table
    op.create_table(
        'copytrade_channels',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('channel_id', sa.String(50), nullable=False),
        sa.Column('confidence_threshold', sa.Integer, server_default='70', nullable=False),
        sa.Column('active', sa.Boolean, server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # copytrade_subscriptions table
    op.create_table(
        'copytrade_subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('profile_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('channel_id', sa.String(50), nullable=False, index=True),
        sa.Column('confidence_threshold', sa.Integer, server_default='70', nullable=False),
        sa.Column('active', sa.Boolean, server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('profile_id', 'channel_id', name='uq_profile_channel_sub'),
    )
    
    # user_sources table (tenant sources)
    op.create_table(
        'user_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('profile_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('source_type', sa.String(20), nullable=False),
        sa.Column('url_or_handle', sa.String(500), nullable=False),
        sa.Column('priority', sa.Integer, default=5),
        sa.Column('tags', sa.String(500), default=""),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('enabled', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('profile_id', 'name', name='uq_profile_source_name'),
        sa.UniqueConstraint('profile_id', 'url_or_handle', name='uq_profile_source_url'),
    )
    
    # admin_sources table (baseline sources)
    op.create_table(
        'admin_sources',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('source_type', sa.String(20), nullable=False),
        sa.Column('url_or_handle', sa.String(500), nullable=False),
        sa.Column('priority', sa.Integer, default=5),
        sa.Column('tags', sa.String(500), default=""),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('enabled', sa.Boolean, default=True),
        sa.Column('is_default', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    
    # Insert default admin sources
    from uuid import uuid4
    conn = op.get_bind()
    conn.execute(sa.text("""
        INSERT INTO admin_sources (id, name, source_type, url_or_handle, priority, tags, description, is_default)
        VALUES 
        (:id1, 'CoinTelegraph', 'rss', 'https://cointelegraph.com/rss', 8, '["general","major"]', 'Leading crypto news outlet', true),
        (:id2, 'Bitcoin Magazine', 'rss', 'https://bitcoinmagazine.com/.rss/full/', 7, '["btc","major"]', 'Bitcoin-focused news', true),
        (:id3, 'VitalikButerin', 'twitter', 'VitalikButerin', 9, '["ethereum","major"]', 'Ethereum founder', true),
        (:id4, 'WHAlerts', 'twitter', 'WHAlerts', 9, '["whale","alerts"]', 'Whale movement alerts', true),
        (:id5, 'CryptoWhale', 'telegram', '@CryptoWhale', 9, '["whale","alerts"]', 'Major whale alerts', true),
        (:id6, 'BitcoinWhale', 'telegram', '@BitcoinWhale', 8, '["bitcoin","whale"]', 'Bitcoin whale tracking', true)
    """), {
        'id1': str(uuid4()),
        'id2': str(uuid4()),
        'id3': str(uuid4()),
        'id4': str(uuid4()),
        'id5': str(uuid4()),
        'id6': str(uuid4()),
    })


def downgrade() -> None:
    op.drop_table('admin_sources')
    op.drop_table('user_sources')
    op.drop_table('copytrade_subscriptions')
    op.drop_table('copytrade_channels')
    op.drop_table('user_sessions')
    op.drop_table('profiles')
