-- ============================================================
-- Portal — Migração 002: Adiciona coluna voice_type em member_roles
-- Versão: 1.0.0 | Data: 2026-05-06
-- ============================================================
-- Necessário quando a tabela member_roles foi criada antes de
-- voice_type ser incluído na migração 001.
-- É seguro re-executar (ADD COLUMN IF NOT EXISTS).
-- ============================================================

BEGIN;

ALTER TABLE member_roles
    ADD COLUMN IF NOT EXISTS voice_type VARCHAR(50) NULL;

COMMIT;
