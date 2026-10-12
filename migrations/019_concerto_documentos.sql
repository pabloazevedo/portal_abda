-- Migration 019: Criar tabela concerto_documentos
-- Vinculação entre Concerto e ArranjoDocumento para distribuição de partituras
-- Data: 2026-06-12

-- Adicionar coluna stab_tipo em arranjo_documentos (se não existir)
ALTER TABLE arranjo_documentos
  ADD COLUMN IF NOT EXISTS stab_tipo VARCHAR(20);

-- Criar tabela concerto_documentos
CREATE TABLE IF NOT EXISTS concerto_documentos (
    id SERIAL PRIMARY KEY,
    concerto_id INTEGER NOT NULL REFERENCES concertos(id) ON DELETE CASCADE,
    arranjo_documento_id INTEGER NOT NULL REFERENCES arranjo_documentos(id) ON DELETE CASCADE,
    instrumento_executando VARCHAR(100),
    musicos_ids JSONB,
    ordem_distribuicao SMALLINT,
    notas_distribuicao TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(concerto_id, arranjo_documento_id)
);

-- Criar índices para performance
CREATE INDEX IF NOT EXISTS idx_concerto_documentos_concerto
  ON concerto_documentos(concerto_id);

CREATE INDEX IF NOT EXISTS idx_concerto_documentos_documento
  ON concerto_documentos(arranjo_documento_id);

-- Comentários
COMMENT ON TABLE concerto_documentos IS 'Vinculação entre Concerto e ArranjoDocumento para distribuição de partituras';
COMMENT ON COLUMN concerto_documentos.instrumento_executando IS 'Nome do instrumento/voz que executa essa parte (ex: Violino 1, Soprano)';
COMMENT ON COLUMN concerto_documentos.musicos_ids IS 'Array JSON de musician_id que executam essa parte';
COMMENT ON COLUMN concerto_documentos.ordem_distribuicao IS 'Ordem na lista de distribuição (1-N)';
COMMENT ON COLUMN concerto_documentos.notas_distribuicao IS 'Notas especiais (ex: Duas cópias, Impressão A3)';
