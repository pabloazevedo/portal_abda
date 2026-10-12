-- ============================================================
-- Portal — Migração 001: Refatoração do Módulo de Membros
-- Versão: 1.0.0 | Data: 2026-05-05
-- Autor: Orchestra Portal
-- ============================================================
-- INSTRUÇÕES:
--   Execute este script em uma transação.
--   É seguro re-executar (usa IF NOT EXISTS / ON CONFLICT).
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. member_type: tornar nullable (legado mantido)
-- ------------------------------------------------------------
ALTER TABLE musicians ALTER COLUMN member_type DROP NOT NULL;

-- Comentários para documentar o legado
COMMENT ON COLUMN musicians.instrument IS '[DEPRECATED] Use member_instruments';
COMMENT ON COLUMN musicians.voice      IS '[DEPRECATED] Use member_instruments (categoria Voz)';
COMMENT ON COLUMN musicians.member_type IS '[DEPRECATED] Use member_roles';

-- ------------------------------------------------------------
-- 2. Enum de papéis (role_type)
-- ------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'role_type') THEN
        CREATE TYPE role_type AS ENUM (
            'musico',
            'maestro',
            'chefe_naipe',
            'arquivista',
            'arranjador',
            'cantor'
        );
    END IF;
END;
$$;

-- ------------------------------------------------------------
-- 3. Tabela master de instrumentos (Single Source of Truth)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS instrumentos_base (
    id         SERIAL       PRIMARY KEY,
    nome       VARCHAR(100) NOT NULL,
    categoria  VARCHAR(80)  NOT NULL,
    ativo      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP    NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_instrumento_nome UNIQUE (nome)
);

CREATE INDEX IF NOT EXISTS idx_instrumento_nome_lower
    ON instrumentos_base (LOWER(nome));

-- ------------------------------------------------------------
-- 4. Tabela de papéis dos membros (COM CORREÇÃO PARA VOICE_TYPE)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS member_roles (
    id             SERIAL        PRIMARY KEY,
    musician_id    INTEGER       NOT NULL
                   REFERENCES musicians(id) ON DELETE CASCADE,
    role_type      role_type     NOT NULL,
    maestro_order  SMALLINT      NULL
                   CHECK (maestro_order IS NULL OR maestro_order BETWEEN 1 AND 9),
    -- COLUNA ADICIONADA PARA RESOLVER O ERRO DO SQLALCHEMY:
    voice_type     VARCHAR(50)   NULL, 
    created_at     TIMESTAMP     NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_member_role UNIQUE (musician_id, role_type)
);

CREATE INDEX IF NOT EXISTS idx_member_roles_musician
    ON member_roles (musician_id);

-- ------------------------------------------------------------
-- 5. Tabela de relação Membro ↔ Instrumento (N para N)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS member_instruments (
    musician_id    INTEGER NOT NULL
                   REFERENCES musicians(id) ON DELETE CASCADE,
    instrumento_id INTEGER NOT NULL
                   REFERENCES instrumentos_base(id),
    PRIMARY KEY (musician_id, instrumento_id)
);

-- ------------------------------------------------------------
-- 6. Migração de dados legados
-- ------------------------------------------------------------

-- 6a. Músicos de orquestra → papel 'musico'
INSERT INTO member_roles (musician_id, role_type)
SELECT id, 'musico'
FROM   musicians
WHERE  member_type IN ('orchestra', 'both')
ON CONFLICT (musician_id, role_type) DO NOTHING;

-- 6b. Membros do coral → papel 'cantor'
INSERT INTO member_roles (musician_id, role_type, voice_type)
SELECT id, 'cantor', voice
FROM   musicians
WHERE  member_type IN ('choir', 'both')
ON CONFLICT (musician_id, role_type) DO NOTHING;

-- 6c. Instrumento legado → member_instruments
INSERT INTO member_instruments (musician_id, instrumento_id)
SELECT m.id, ib.id
FROM   musicians m
JOIN   instrumentos_base ib
    ON ib.nome ILIKE TRIM(SPLIT_PART(m.instrument, '/', 1)) || '%'
WHERE  m.instrument IS NOT NULL
  AND  m.instrument <> ''
ON CONFLICT DO NOTHING;

COMMIT;

-- ============================================================
-- ROLLBACK (para desfazer — execute manualmente se necessário)
-- ============================================================
-- BEGIN;
-- DROP TABLE IF EXISTS member_instruments;
-- DROP TABLE IF EXISTS member_roles;
-- DROP TABLE IF EXISTS instrumentos_base;
-- DROP TYPE IF EXISTS role_type;
-- ALTER TABLE musicians ALTER COLUMN member_type SET NOT NULL;
-- COMMIT;
