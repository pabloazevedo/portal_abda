-- ============================================================
-- 009_identificacao_hibrida.sql — Suporte a múltiplas etiquetas
-- físicas e auditoria append-only de patrimônio.
-- Fases aplicadas: 1 (QR Code) e 2 (Barcode 1D / Data Matrix)
-- Data: 2026-05-10
-- ============================================================

-- ── Tipo ENUM para tecnologia de etiqueta ───────────────────
DO $$ BEGIN
    CREATE TYPE etiqueta_tipo_enum AS ENUM (
        'qr', 'barcode_1d', 'data_matrix', 'rfid_hf', 'rfid_uhf'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── Tabela de etiquetas físicas (N por item) ────────────────
CREATE TABLE IF NOT EXISTS patrimonio_etiqueta (
    id            SERIAL             PRIMARY KEY,
    patrimonio_id UUID               NOT NULL REFERENCES patrimonio(id) ON DELETE CASCADE,
    tipo          etiqueta_tipo_enum NOT NULL,
    valor         VARCHAR(255)       NOT NULL,
    ativo         BOOLEAN            NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ        NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_etiqueta_valor UNIQUE (tipo, valor)
);

COMMENT ON COLUMN patrimonio_etiqueta.valor IS
    'Para qr/barcode: UUID do item. Para rfid_hf/rfid_uhf: EPC da tag física.';
COMMENT ON COLUMN patrimonio_etiqueta.ativo IS
    'FALSE quando a etiqueta é substituída — mantém histórico sem DELETE.';

CREATE INDEX IF NOT EXISTS idx_etiqueta_patrimonio ON patrimonio_etiqueta(patrimonio_id);
CREATE INDEX IF NOT EXISTS idx_etiqueta_valor      ON patrimonio_etiqueta(valor);
CREATE INDEX IF NOT EXISTS idx_etiqueta_ativo      ON patrimonio_etiqueta(patrimonio_id)
    WHERE ativo = TRUE;

-- ── Tabela de auditoria append-only ─────────────────────────
CREATE TABLE IF NOT EXISTS patrimonio_auditoria (
    id            BIGSERIAL   PRIMARY KEY,
    patrimonio_id UUID        NOT NULL,
    acao          VARCHAR(50) NOT NULL,
    usuario_id    INTEGER     REFERENCES users(id) ON DELETE SET NULL,
    payload       JSONB       NOT NULL DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE patrimonio_auditoria IS
    'Log imutável de eventos. Nunca atualizar ou deletar linhas desta tabela.';
COMMENT ON COLUMN patrimonio_auditoria.patrimonio_id IS
    'Sem FK intencional: preserva histórico mesmo após exclusão do item.';

CREATE INDEX IF NOT EXISTS idx_auditoria_patrimonio ON patrimonio_auditoria(patrimonio_id);
CREATE INDEX IF NOT EXISTS idx_auditoria_created    ON patrimonio_auditoria(created_at DESC);

-- ── Regras de proteção: impedem DELETE/UPDATE na auditoria ──
CREATE OR REPLACE RULE no_delete_auditoria AS
    ON DELETE TO patrimonio_auditoria DO INSTEAD NOTHING;

CREATE OR REPLACE RULE no_update_auditoria AS
    ON UPDATE TO patrimonio_auditoria DO INSTEAD NOTHING;

-- ── Backfill: registra etiqueta QR para todos os itens existentes ──
INSERT INTO patrimonio_etiqueta (patrimonio_id, tipo, valor)
SELECT id, 'qr', id::TEXT
FROM   patrimonio
ON CONFLICT (tipo, valor) DO NOTHING;
