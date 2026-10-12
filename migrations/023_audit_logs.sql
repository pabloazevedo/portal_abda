-- Auditoria do sistema + retenção configurável
ALTER TABLE configuracoes
  ADD COLUMN IF NOT EXISTS audit_retention_days INTEGER NOT NULL DEFAULT 90;

CREATE TABLE IF NOT EXISTS audit_logs (
  id              SERIAL PRIMARY KEY,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  actor_user_id   INTEGER NULL,
  actor_username  VARCHAR(100) NULL,
  action          VARCHAR(80) NOT NULL,
  entity_type     VARCHAR(80) NULL,
  entity_id       VARCHAR(80) NULL,
  summary         VARCHAR(500) NULL,
  ip              VARCHAR(64) NULL,
  request_id      VARCHAR(64) NULL,
  meta_json       TEXT NULL
);

CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at ON audit_logs (created_at);
CREATE INDEX IF NOT EXISTS ix_audit_logs_actor_user_id ON audit_logs (actor_user_id);
CREATE INDEX IF NOT EXISTS ix_audit_logs_action ON audit_logs (action);
CREATE INDEX IF NOT EXISTS ix_audit_logs_entity_type ON audit_logs (entity_type);
