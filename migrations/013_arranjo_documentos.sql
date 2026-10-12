-- Migration 013: Arranjo Documentos
-- Tabela para armazenar múltiplos documentos (grade, partes, etc) por arranjo
-- Data: 2026-06-12

CREATE TABLE IF NOT EXISTS arranjo_documentos (
    id SERIAL PRIMARY KEY,
    arranjo_id INTEGER NOT NULL REFERENCES arranjos(id) ON DELETE CASCADE,
    tipo VARCHAR(50) NOT NULL,
    instrumento_id INTEGER REFERENCES instrumentos_base(id) ON DELETE SET NULL,
    versao VARCHAR(20) NOT NULL DEFAULT 'v1.0',
    arquivo_s3_key VARCHAR(500) NOT NULL UNIQUE,
    tamanho_bytes INTEGER,
    hash_arquivo VARCHAR(64),
    ativo BOOLEAN DEFAULT TRUE NOT NULL,
    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,

    UNIQUE(arranjo_id, tipo, versao)
);

CREATE INDEX idx_arranjo_documentos_arranjo_id ON arranjo_documentos(arranjo_id);
CREATE INDEX idx_arranjo_documentos_tipo ON arranjo_documentos(tipo);
CREATE INDEX idx_arranjo_documentos_ativo ON arranjo_documentos(ativo);
CREATE INDEX idx_arranjo_documentos_s3_key ON arranjo_documentos(arquivo_s3_key);

COMMENT ON TABLE arranjo_documentos IS 'Documentos (arquivos) vinculados a arranjos: grades, partes, SATB, etc';
COMMENT ON COLUMN arranjo_documentos.tipo IS 'Tipo: grade, parte_instrumento, satb_soprano, satb_alto, etc';
COMMENT ON COLUMN arranjo_documentos.arquivo_s3_key IS 'Caminho no S3: obras/arranjo_123/grade/v1.0/file.pdf';
COMMENT ON COLUMN arranjo_documentos.hash_arquivo IS 'SHA256 do arquivo para deduplicação';
