-- ============================================================
-- 013_acervo_separacao.sql — Acervo: separação Obras / Arranjos
-- Data: 2026-05-18
-- ============================================================

-- Torna obra_id opcional em arranjos (arranjo pode existir sem obra)
ALTER TABLE arranjos ALTER COLUMN obra_id DROP NOT NULL;

-- Troca RESTRICT por SET NULL na FK: ao excluir uma obra,
-- arranjos associados tornam-se "autônomos" (obra_id = NULL)
ALTER TABLE arranjos DROP CONSTRAINT IF EXISTS arranjos_obra_id_fkey;
ALTER TABLE arranjos
    ADD CONSTRAINT arranjos_obra_id_fkey
    FOREIGN KEY (obra_id) REFERENCES obras(id) ON DELETE SET NULL;
