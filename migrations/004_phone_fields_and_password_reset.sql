-- ============================================================
-- Portal — Migração 004: Campos de telefone e recuperação de senha
-- Versão: 1.0.0 | Data: 2026-05-07
-- ============================================================

BEGIN;

-- 1. Tornar phone nullable (era NOT NULL)
ALTER TABLE musicians ALTER COLUMN phone DROP NOT NULL;

-- 2. Adicionar campos de telefone separados
ALTER TABLE musicians ADD COLUMN IF NOT EXISTS celular  VARCHAR(20) NULL;
ALTER TABLE musicians ADD COLUMN IF NOT EXISTS telefone VARCHAR(20) NULL;

-- 3. Migrar dados legados: copiar phone para celular
UPDATE musicians SET celular = phone WHERE celular IS NULL AND phone IS NOT NULL;

-- 4. Tabela de tokens de recuperação de senha
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id         SERIAL      PRIMARY KEY,
    user_id    INTEGER     NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(64) NOT NULL UNIQUE,
    expires_at TIMESTAMP   NOT NULL,
    used_at    TIMESTAMP   NULL,
    created_at TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_prt_token_hash ON password_reset_tokens (token_hash);
CREATE INDEX IF NOT EXISTS idx_prt_user_id    ON password_reset_tokens (user_id);

COMMIT;
