-- ============================================================
-- 005_patrimonio.sql — Módulo de Inventário de Patrimônio
-- Data: 2026-05-07
-- ============================================================

-- Tipos de item
DO $$ BEGIN
    CREATE TYPE tipo_item_enum AS ENUM (
        'Instrumento', 'Movel', 'Eletronico', 'Partitura', 'Decoracao', 'Outros'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Status do patrimônio
DO $$ BEGIN
    CREATE TYPE status_patrimonio_enum AS ENUM (
        'Disponivel', 'Emprestado', 'Manutencao', 'Baixa'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ============================================================
-- Tabela principal de patrimônio
-- ============================================================
CREATE TABLE IF NOT EXISTS patrimonio (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tipo_item             tipo_item_enum NOT NULL,
    identificador_interno VARCHAR(50)  UNIQUE NOT NULL,
    fabricante            VARCHAR(200),
    modelo                VARCHAR(200),
    ano_compra            SMALLINT,
    valor_mercado         NUMERIC(12,2),
    status                status_patrimonio_enum NOT NULL DEFAULT 'Disponivel',
    detalhes              JSONB,          -- campos específicos por tipo de item
    observacoes           TEXT,
    created_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at            TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON COLUMN patrimonio.identificador_interno IS 'Código único gerado para QR Code (ex: INS-202605-0001)';
COMMENT ON COLUMN patrimonio.detalhes IS 'JSONB com campos específicos: Instrumento={categoria_familia,ano_fabricacao,avaliacao_condicao}, Partitura={compositor,arranjador,nome_obra}, Decoracao={descricao_livre,local_armazenamento}';

-- ============================================================
-- Tabela de empréstimos (vínculo patrimônio ↔ músico)
-- ============================================================
CREATE TABLE IF NOT EXISTS patrimonio_emprestimo (
    id              SERIAL PRIMARY KEY,
    patrimonio_id   UUID    NOT NULL REFERENCES patrimonio(id) ON DELETE CASCADE,
    musician_id     INTEGER NOT NULL REFERENCES musicians(id) ON DELETE CASCADE,
    data_emprestimo TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    data_devolucao  TIMESTAMP WITH TIME ZONE,   -- NULL = ainda com o músico
    observacoes     TEXT,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

COMMENT ON COLUMN patrimonio_emprestimo.data_devolucao IS 'NULL enquanto o item estiver emprestado. Preenchido na devolução.';

-- ============================================================
-- Índices
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_patrimonio_tipo      ON patrimonio(tipo_item);
CREATE INDEX IF NOT EXISTS idx_patrimonio_status    ON patrimonio(status);
CREATE INDEX IF NOT EXISTS idx_patrimonio_id_interno ON patrimonio(identificador_interno);

CREATE INDEX IF NOT EXISTS idx_emprestimo_patrimonio ON patrimonio_emprestimo(patrimonio_id);
CREATE INDEX IF NOT EXISTS idx_emprestimo_musician   ON patrimonio_emprestimo(musician_id);
-- Índice parcial: apenas vínculos ativos (sem devolução)
CREATE INDEX IF NOT EXISTS idx_emprestimo_ativo      ON patrimonio_emprestimo(patrimonio_id)
    WHERE data_devolucao IS NULL;
