-- Migration 015: Auditoria Compartilhamento
-- Log de todos os acessos (quem, quando, de onde)
-- Data: 2026-06-12

CREATE TABLE IF NOT EXISTS auditoria_compartilhamento (
    id SERIAL PRIMARY KEY,
    compartilhamento_id INTEGER NOT NULL REFERENCES compartilhamento_arranjos(id) ON DELETE CASCADE,
    acao VARCHAR(50) NOT NULL,
    musician_id INTEGER REFERENCES musicians(id) ON DELETE SET NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    metadata_json JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX idx_auditoria_compartilhamento_id ON auditoria_compartilhamento(compartilhamento_id);
CREATE INDEX idx_auditoria_acao ON auditoria_compartilhamento(acao);
CREATE INDEX idx_auditoria_musician ON auditoria_compartilhamento(musician_id);
CREATE INDEX idx_auditoria_created ON auditoria_compartilhamento(created_at);

COMMENT ON TABLE auditoria_compartilhamento IS 'Log imutável de acessos a documentos compartilhados';
COMMENT ON COLUMN auditoria_compartilhamento.acao IS 'Ação: acesso_iniciado, download_iniciado, download_completo, expirado, revogado';
COMMENT ON COLUMN auditoria_compartilhamento.ip_address IS 'IP do cliente para detectar abuso';
COMMENT ON COLUMN auditoria_compartilhamento.metadata_json IS 'Dados adicionais (referer, accept, etc)';
