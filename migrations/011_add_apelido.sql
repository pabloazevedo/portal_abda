-- ============================================================
-- 011_add_apelido.sql — Adiciona campo opcional "apelido" a musicians
-- Data: 2026-05-17
-- ============================================================

ALTER TABLE musicians
    ADD COLUMN IF NOT EXISTS apelido VARCHAR(100);

COMMENT ON COLUMN musicians.apelido IS 'Apelido ou nome artístico do membro (opcional).';
