-- Migration 006 — Sequências PostgreSQL por tipo de item de patrimônio (R-01)
-- Substitui COUNT(*) em _gerar_identificador para eliminar race condition.
-- Cada tipo tem sua própria sequência, cujo valor inicial parte do total atual.

DO $$
DECLARE
  cnt INTEGER;
BEGIN
  SELECT GREATEST(COUNT(*), 0) INTO cnt FROM patrimonio WHERE tipo_item = 'Instrumento';
  IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE sequencename = 'seq_patrimonio_ins') THEN
    EXECUTE format('CREATE SEQUENCE seq_patrimonio_ins START WITH %s', cnt + 1);
  END IF;

  SELECT GREATEST(COUNT(*), 0) INTO cnt FROM patrimonio WHERE tipo_item = 'Movel';
  IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE sequencename = 'seq_patrimonio_mov') THEN
    EXECUTE format('CREATE SEQUENCE seq_patrimonio_mov START WITH %s', cnt + 1);
  END IF;

  SELECT GREATEST(COUNT(*), 0) INTO cnt FROM patrimonio WHERE tipo_item = 'Eletronico';
  IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE sequencename = 'seq_patrimonio_ele') THEN
    EXECUTE format('CREATE SEQUENCE seq_patrimonio_ele START WITH %s', cnt + 1);
  END IF;

  SELECT GREATEST(COUNT(*), 0) INTO cnt FROM patrimonio WHERE tipo_item = 'Partitura';
  IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE sequencename = 'seq_patrimonio_par') THEN
    EXECUTE format('CREATE SEQUENCE seq_patrimonio_par START WITH %s', cnt + 1);
  END IF;

  SELECT GREATEST(COUNT(*), 0) INTO cnt FROM patrimonio WHERE tipo_item = 'Decoracao';
  IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE sequencename = 'seq_patrimonio_dec') THEN
    EXECUTE format('CREATE SEQUENCE seq_patrimonio_dec START WITH %s', cnt + 1);
  END IF;

  SELECT GREATEST(COUNT(*), 0) INTO cnt FROM patrimonio WHERE tipo_item = 'Outros';
  IF NOT EXISTS (SELECT 1 FROM pg_sequences WHERE sequencename = 'seq_patrimonio_out') THEN
    EXECUTE format('CREATE SEQUENCE seq_patrimonio_out START WITH %s', cnt + 1);
  END IF;
END $$;
