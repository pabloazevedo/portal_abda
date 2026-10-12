-- Migration 020: Links de acesso a partituras por evento/músico
-- Permite distribuir partituras via link para o dia do evento
-- Data: 2026-07-12

CREATE TABLE IF NOT EXISTS concerto_acesso_partituras (
    id SERIAL PRIMARY KEY,
    concerto_id INTEGER NOT NULL REFERENCES concertos(id) ON DELETE CASCADE,
    musician_id INTEGER NOT NULL REFERENCES musicians(id) ON DELETE CASCADE,
    token UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    documento_ids JSONB NOT NULL DEFAULT '[]',
    expires_at TIMESTAMPTZ NOT NULL,
    enviado_em TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(concerto_id, musician_id)
);

CREATE INDEX IF NOT EXISTS idx_concerto_acesso_token
  ON concerto_acesso_partituras(token);

CREATE INDEX IF NOT EXISTS idx_concerto_acesso_concerto
  ON concerto_acesso_partituras(concerto_id);

COMMENT ON TABLE concerto_acesso_partituras IS 'Link de acesso individual para músico baixar partituras do evento';
COMMENT ON COLUMN concerto_acesso_partituras.documento_ids IS 'Array JSON de arranjo_documentos.id liberados para o músico';
COMMENT ON COLUMN concerto_acesso_partituras.expires_at IS 'Expiração do link (tipicamente fim do dia do evento + 1 dia)';
