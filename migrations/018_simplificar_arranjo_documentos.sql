-- Migration 018: Simplificar ArranjoDocumento
-- Remove colunas desnecessárias e alinha com nova arquitetura
-- Data: 2026-06-12

-- Remover tabelas de auditoria e validação (agora usando SQLite FTS)
DROP TABLE IF EXISTS auditoria_validacao_documento CASCADE;
DROP TABLE IF EXISTS auditoria_compartilhamento CASCADE;
DROP TABLE IF EXISTS compositores CASCADE;

-- Remover constraints e colunas desnecessárias da tabela arranjo_documentos
ALTER TABLE arranjo_documentos
  DROP CONSTRAINT IF EXISTS arranjo_documentos_instrumento_id_fkey,
  DROP COLUMN IF EXISTS versao,
  DROP COLUMN IF EXISTS hash_arquivo,
  DROP COLUMN IF EXISTS instrumento_id,
  DROP COLUMN IF EXISTS ativo,
  DROP COLUMN IF EXISTS updated_at;

-- Renomear coluna arquivo_s3_key para arquivo_caminho
ALTER TABLE arranjo_documentos
  RENAME COLUMN arquivo_s3_key TO arquivo_caminho;

-- Adicionar coluna para instrumento_nome (se não existir)
ALTER TABLE arranjo_documentos
  ADD COLUMN IF NOT EXISTS instrumento_nome VARCHAR(100);

-- Remover constraint UNIQUE de arquivo_caminho (agora pode haver duplicatas em estrutura de diretórios)
ALTER TABLE arranjo_documentos
  DROP CONSTRAINT IF EXISTS arranjo_documentos_arquivo_s3_key_key;

-- Criar índice em arquivo_caminho para performance
CREATE INDEX IF NOT EXISTS idx_arranjo_documentos_caminho
  ON arranjo_documentos(arquivo_caminho);

-- Remover constraint UNIQUE se existir em enums (eles foram deletados)
DROP TYPE IF EXISTS tipo_documento_enum CASCADE;
DROP TYPE IF EXISTS tipo_compartilhamento_enum CASCADE;
DROP TYPE IF EXISTS status_compartilhamento_enum CASCADE;

COMMENT ON TABLE arranjo_documentos IS 'Documentos de arranjos (grades, partes, coral, etc)';
COMMENT ON COLUMN arranjo_documentos.tipo IS 'Tipo: grade, instrumento, coral, acompanhamento';
COMMENT ON COLUMN arranjo_documentos.instrumento_nome IS 'Nome do instrumento (ex: Violino 1, Soprano)';
COMMENT ON COLUMN arranjo_documentos.arquivo_caminho IS 'Caminho do arquivo em disco (ex: obras/123/grade/score.pdf)';
