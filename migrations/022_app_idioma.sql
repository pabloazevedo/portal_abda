-- Migration 022: idioma global da aplicação (admin)
-- Data: 2026-08-02

ALTER TABLE configuracoes
  ADD COLUMN IF NOT EXISTS idioma VARCHAR(5) NOT NULL DEFAULT 'pt';

COMMENT ON COLUMN configuracoes.idioma IS
  'Idioma da UI (pt|en|es). Definido apenas pelo administrador.';
