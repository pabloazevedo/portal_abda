-- Histórico de versões / release notes do portal
CREATE TABLE IF NOT EXISTS release_notes (
  id           SERIAL PRIMARY KEY,
  version      VARCHAR(32)  NOT NULL UNIQUE,
  title        VARCHAR(200) NOT NULL DEFAULT '',
  notes        TEXT         NOT NULL DEFAULT '',
  released_at  DATE         NOT NULL,
  is_current   BOOLEAN      NOT NULL DEFAULT FALSE,
  created_by   INTEGER      NULL REFERENCES users(id) ON DELETE SET NULL,
  created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_release_notes_released_at ON release_notes (released_at);
CREATE INDEX IF NOT EXISTS ix_release_notes_version ON release_notes (version);

-- Seed da versão inicial (só se a tabela estiver vazia)
INSERT INTO release_notes (version, title, notes, released_at, is_current)
SELECT
  '1.0.0',
  'Lançamento inicial',
  E'• Portal do Membro disponível para a associação\n• Gestão de membros, papéis e instrumentos\n• Inventário de patrimônio com etiquetas\n• Acervo musical (obras, arranjos e programação)\n• Configurações institucionais e branding',
  CURRENT_DATE,
  TRUE
WHERE NOT EXISTS (SELECT 1 FROM release_notes LIMIT 1);
