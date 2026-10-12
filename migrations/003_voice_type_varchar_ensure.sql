-- ============================================================
-- Portal — Migração 003: Garante voice_type como VARCHAR(50)
-- Versão: 1.0.0 | Data: 2026-05-06
-- ============================================================
-- O modelo SQLAlchemy agora usa native_enum=False (VARCHAR).
-- Se existir um tipo PostgreSQL chamado "voice_type", ele
-- não conflita pois a coluna já é VARCHAR — mas se a coluna
-- tiver sido criada como enum nativo, este script a converte.
-- É seguro re-executar.
-- ============================================================

BEGIN;

DO $$
BEGIN
    -- Converte a coluna para VARCHAR caso esteja como tipo enum nativo
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'member_roles'
          AND column_name = 'voice_type'
          AND data_type = 'USER-DEFINED'
    ) THEN
        ALTER TABLE member_roles
            ALTER COLUMN voice_type TYPE VARCHAR(50)
            USING voice_type::text;
    END IF;
END;
$$;

COMMIT;
