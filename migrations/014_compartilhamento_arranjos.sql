-- Migration 014: Compartilhamento Arranjos
-- Registros de compartilhamento: quem tem acesso a qual documento
-- Data: 2026-06-12

CREATE TABLE IF NOT EXISTS compartilhamento_arranjos (
    id SERIAL PRIMARY KEY,
    arranjo_documento_id INTEGER NOT NULL REFERENCES arranjo_documentos(id) ON DELETE CASCADE,
    concerto_id INTEGER REFERENCES concertos(id) ON DELETE SET NULL,
    musician_id INTEGER REFERENCES musicians(id) ON DELETE SET NULL,
    access_type VARCHAR(50) NOT NULL DEFAULT 'download'
        CHECK (access_type IN ('visualizacao', 'download', 'impressao_apenas')),
    status VARCHAR(50) NOT NULL DEFAULT 'ativo'
        CHECK (status IN ('ativo', 'expirado', 'revogado', 'pendente')),
    token_acesso VARCHAR(255) UNIQUE NOT NULL,
    data_liberacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    data_expiracao TIMESTAMP,
    criado_por INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_compartilhamento_token ON compartilhamento_arranjos(token_acesso);
CREATE INDEX idx_compartilhamento_musician ON compartilhamento_arranjos(musician_id);
CREATE INDEX idx_compartilhamento_status ON compartilhamento_arranjos(status);
CREATE INDEX idx_compartilhamento_documento ON compartilhamento_arranjos(arranjo_documento_id);
CREATE INDEX idx_compartilhamento_concerto ON compartilhamento_arranjos(concerto_id);

COMMENT ON TABLE compartilhamento_arranjos IS 'Registros de compartilhamento de documentos com músicos';
COMMENT ON COLUMN compartilhamento_arranjos.token_acesso IS 'Token único para acesso público (sem login)';
COMMENT ON COLUMN compartilhamento_arranjos.data_expiracao IS 'Quando acesso expira (NULL = nunca expira)';
COMMENT ON COLUMN compartilhamento_arranjos.musician_id IS 'Específico para um músico, ou NULL para todos';
