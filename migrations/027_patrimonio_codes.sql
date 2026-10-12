-- QR e código de barras gerados pelo sistema no cadastro do item
ALTER TABLE patrimonio
  ADD COLUMN IF NOT EXISTS qr_payload    VARCHAR(512),
  ADD COLUMN IF NOT EXISTS barcode_value VARCHAR(64);

CREATE UNIQUE INDEX IF NOT EXISTS ux_patrimonio_barcode_value
  ON patrimonio (barcode_value)
  WHERE barcode_value IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_patrimonio_qr_payload ON patrimonio (qr_payload);

-- Backfill: itens já existentes
UPDATE patrimonio
SET
  qr_payload    = COALESCE(qr_payload, '/patrimonio/scan/' || id::text),
  barcode_value = COALESCE(barcode_value, identificador_interno)
WHERE qr_payload IS NULL OR barcode_value IS NULL;

-- Reativa etiquetas inativas com o mesmo (tipo, valor) — evita uq_etiqueta_valor
UPDATE patrimonio_etiqueta e
SET patrimonio_id = p.id, ativo = TRUE
FROM patrimonio p
WHERE e.tipo = 'qr'::etiqueta_tipo_enum
  AND e.valor = p.id::text
  AND e.ativo = FALSE;

UPDATE patrimonio_etiqueta e
SET patrimonio_id = p.id, ativo = TRUE
FROM patrimonio p
WHERE e.tipo = 'barcode_1d'::etiqueta_tipo_enum
  AND e.valor = p.barcode_value
  AND e.ativo = FALSE
  AND p.barcode_value IS NOT NULL;

-- Insere apenas se ainda não existir o par (tipo, valor)
INSERT INTO patrimonio_etiqueta (patrimonio_id, tipo, valor, ativo, created_at)
SELECT p.id, 'qr'::etiqueta_tipo_enum, p.id::text, TRUE, NOW()
FROM patrimonio p
WHERE NOT EXISTS (
  SELECT 1 FROM patrimonio_etiqueta e
  WHERE e.tipo = 'qr' AND e.valor = p.id::text
);

INSERT INTO patrimonio_etiqueta (patrimonio_id, tipo, valor, ativo, created_at)
SELECT p.id, 'barcode_1d'::etiqueta_tipo_enum, p.barcode_value, TRUE, NOW()
FROM patrimonio p
WHERE p.barcode_value IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM patrimonio_etiqueta e
    WHERE e.tipo = 'barcode_1d' AND e.valor = p.barcode_value
  );
