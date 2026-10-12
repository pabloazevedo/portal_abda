-- ============================================================
-- 010_rbac_roles.sql — RBAC granular: papéis Arquivista, Maestro e Secretaria
-- Adiciona novos valores ao enum userrole do PostgreSQL.
-- Data: 2026-05-10
-- ============================================================

-- ALTER TYPE ADD VALUE é DDL não-transacional no PostgreSQL.
-- Cada ADD VALUE é idempotente via verificação em pg_enum.

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        WHERE enumlabel = 'maestro'
          AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole')
    ) THEN
        ALTER TYPE userrole ADD VALUE 'maestro';
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        WHERE enumlabel = 'arquivista'
          AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole')
    ) THEN
        ALTER TYPE userrole ADD VALUE 'arquivista';
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        WHERE enumlabel = 'secretaria'
          AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'userrole')
    ) THEN
        ALTER TYPE userrole ADD VALUE 'secretaria';
    END IF;
END $$;

COMMENT ON TYPE userrole IS
    'Papéis de sistema: admin (acesso total), maestro (gestão artística + membros), '
    'arquivista (gestão de patrimônio e acervo), secretaria (gestão de membros), '
    'user (somente leitura).';
