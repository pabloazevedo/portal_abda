-- Migration 007 — Torna Musician.celular NOT NULL (I-01)
-- Alinha a constraint do banco com a validação obrigatória da camada de aplicação.
-- Registros legados sem celular recebem string vazia antes da constraint.

UPDATE musicians SET celular = '' WHERE celular IS NULL;

ALTER TABLE musicians ALTER COLUMN celular SET NOT NULL;
ALTER TABLE musicians ALTER COLUMN celular SET DEFAULT '';
