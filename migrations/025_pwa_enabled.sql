-- Site mobile / PWA: flag global (admin)
ALTER TABLE configuracoes
  ADD COLUMN IF NOT EXISTS pwa_enabled BOOLEAN NOT NULL DEFAULT FALSE;
