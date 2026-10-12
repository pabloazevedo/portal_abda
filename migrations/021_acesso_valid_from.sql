-- Migration 021: Janela de validade (valid_from) para links de partituras
-- Download liberado a partir do dia do evento até expires_at
-- Data: 2026-07-30

ALTER TABLE concerto_acesso_partituras
  ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ;

-- Backfill: início do dia UTC de data_inicio do concerto
UPDATE concerto_acesso_partituras a
SET valid_from = date_trunc('day', c.data_inicio AT TIME ZONE 'UTC')
FROM concertos c
WHERE c.id = a.concerto_id
  AND a.valid_from IS NULL;

COMMENT ON COLUMN concerto_acesso_partituras.valid_from IS
  'Início da janela de download (tipicamente início do dia do evento)';
