-- Migration 008: Tabela de configurações gerais (rodapé e dados institucionais).
-- Usa uma única linha protegida por CHECK (id = 1).

CREATE TABLE IF NOT EXISTS configuracoes (
  id                 INTEGER PRIMARY KEY CHECK (id = 1),
  nome_institucional VARCHAR(200) NOT NULL DEFAULT '',
  endereco           TEXT         NOT NULL DEFAULT '',
  link_estatuto      VARCHAR(500) NOT NULL DEFAULT '',
  link_repositorio   VARCHAR(500) NOT NULL DEFAULT ''
);

-- Garante que a linha singleton exista
INSERT INTO configuracoes (id, nome_institucional, endereco, link_estatuto, link_repositorio)
VALUES (1, '', '', '', '')
ON CONFLICT (id) DO NOTHING;
