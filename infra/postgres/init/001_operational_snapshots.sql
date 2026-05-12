CREATE TABLE IF NOT EXISTS operational_snapshots (
    snapshot_id VARCHAR(255) PRIMARY KEY,
    entity_type VARCHAR(128) NOT NULL,
    entity_id VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    payload JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_operational_snapshot_version
    ON operational_snapshots (entity_type, entity_id, version);

CREATE INDEX IF NOT EXISTS ix_operational_snapshots_entity_type
    ON operational_snapshots (entity_type);

CREATE INDEX IF NOT EXISTS ix_operational_snapshots_entity_id
    ON operational_snapshots (entity_id);
