-- ============================================================
-- 012_acervo_musical.sql — Módulo de Acervo Musical
-- Data: 2026-05-18
-- Tabelas: obras, arranjos, concertos, concerto_arranjos
-- ============================================================

-- ── Enums ──────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE genero_musical_enum AS ENUM (
        'sinfonia', 'concerto', 'camara', 'coral', 'opera',
        'sacra', 'popular', 'folclorica', 'contemporanea', 'outro'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE copyright_status_enum AS ENUM (
        'dominio_publico',
        'licenciado',
        'pendente'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── Tabela: obras ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS obras (
    id               SERIAL PRIMARY KEY,
    titulo           VARCHAR(300) NOT NULL,
    titulo_original  VARCHAR(300),
    compositor_id    INTEGER REFERENCES musicians(id) ON DELETE SET NULL,
    compositor_nome  VARCHAR(200),
    genero           genero_musical_enum NOT NULL DEFAULT 'outro',
    tonalidade       VARCHAR(20),
    ano_composicao   SMALLINT,
    observacoes      TEXT,
    created_by       INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_compositor CHECK (
        compositor_id IS NOT NULL OR compositor_nome IS NOT NULL
    )
);

COMMENT ON TABLE  obras IS 'Entidade central do acervo musical — obra intelectual independente de arranjo';
COMMENT ON COLUMN obras.compositor_id   IS 'Membro interno; mutuamente exclusivo mas não obrigatório com compositor_nome';
COMMENT ON COLUMN obras.compositor_nome IS 'Compositor externo (ex: Beethoven, Bach)';

CREATE INDEX IF NOT EXISTS idx_obras_titulo_fts
    ON obras USING gin(to_tsvector('portuguese', titulo));
CREATE INDEX IF NOT EXISTS idx_obras_compositor_id ON obras(compositor_id);
CREATE INDEX IF NOT EXISTS idx_obras_genero        ON obras(genero);

-- ── Tabela: arranjos ────────────────────────────────────────

CREATE TABLE IF NOT EXISTS arranjos (
    id                 SERIAL PRIMARY KEY,
    obra_id            INTEGER NOT NULL REFERENCES obras(id) ON DELETE RESTRICT,
    titulo_arranjo     VARCHAR(300),
    arranjador_id      INTEGER REFERENCES musicians(id) ON DELETE SET NULL,
    arranjador_nome    VARCHAR(200),
    instrumentacao     TEXT NOT NULL,
    duracao_segundos   INTEGER,
    editora            VARCHAR(200),
    copyright_status   copyright_status_enum NOT NULL DEFAULT 'pendente',
    numero_licenca     VARCHAR(100),
    arquivo_partitura  VARCHAR(500),
    patrimonio_id      UUID REFERENCES patrimonio(id) ON DELETE SET NULL,
    ativo              BOOLEAN NOT NULL DEFAULT TRUE,
    created_by         INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at         TIMESTAMPTZ DEFAULT NOW(),
    updated_at         TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON COLUMN arranjos.obra_id           IS 'RESTRICT: não permite excluir obra com arranjos';
COMMENT ON COLUMN arranjos.duracao_segundos  IS 'Duração total em segundos; use div/mod para MM:SS';
COMMENT ON COLUMN arranjos.arquivo_partitura IS 'Caminho relativo em /uploads/partituras/';
COMMENT ON COLUMN arranjos.patrimonio_id     IS 'FK opcional para cópia física no módulo de patrimônio';

CREATE INDEX IF NOT EXISTS idx_arranjos_obra_id
    ON arranjos(obra_id);
CREATE INDEX IF NOT EXISTS idx_arranjos_arranjador_id
    ON arranjos(arranjador_id);
CREATE INDEX IF NOT EXISTS idx_arranjos_instrumentacao_fts
    ON arranjos USING gin(to_tsvector('portuguese', instrumentacao));
CREATE INDEX IF NOT EXISTS idx_arranjos_copyright
    ON arranjos(copyright_status);
CREATE INDEX IF NOT EXISTS idx_arranjos_ativo
    ON arranjos(obra_id) WHERE ativo = TRUE;

-- ── Tabela: concertos ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS concertos (
    id          SERIAL PRIMARY KEY,
    titulo      VARCHAR(300) NOT NULL,
    data_inicio TIMESTAMPTZ NOT NULL,
    data_fim    TIMESTAMPTZ,
    local       VARCHAR(300),
    maestro_id  INTEGER REFERENCES musicians(id) ON DELETE SET NULL,
    descricao   TEXT,
    publico     BOOLEAN NOT NULL DEFAULT TRUE,
    cal_uid     UUID    NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    created_by  INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON COLUMN concertos.publico  IS 'TRUE = visível no feed iCal público /acervo/calendario.ics';
COMMENT ON COLUMN concertos.cal_uid  IS 'UID estável para VEVENT no feed iCal (RFC 5545)';

CREATE INDEX IF NOT EXISTS idx_concertos_data      ON concertos(data_inicio);
CREATE INDEX IF NOT EXISTS idx_concertos_maestro   ON concertos(maestro_id);

-- ── Tabela: concerto_arranjos (programa + execução) ─────────

CREATE TABLE IF NOT EXISTS concerto_arranjos (
    id              SERIAL PRIMARY KEY,
    concerto_id     INTEGER NOT NULL REFERENCES concertos(id) ON DELETE CASCADE,
    arranjo_id      INTEGER NOT NULL REFERENCES arranjos(id)  ON DELETE RESTRICT,
    ordem           SMALLINT,
    data_execucao   TIMESTAMPTZ,
    duracao_real_s  INTEGER,
    observacoes     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (concerto_id, arranjo_id)
);

COMMENT ON COLUMN concerto_arranjos.data_execucao  IS 'NULL = planejado; preenchido pós-concerto pelo maestro';
COMMENT ON COLUMN concerto_arranjos.duracao_real_s IS 'Duração real executada (pode diferir do arranjo)';

CREATE INDEX IF NOT EXISTS idx_ca_concerto    ON concerto_arranjos(concerto_id);
CREATE INDEX IF NOT EXISTS idx_ca_arranjo     ON concerto_arranjos(arranjo_id);
-- índice parcial para queries de histórico (execuções confirmadas)
CREATE INDEX IF NOT EXISTS idx_ca_executadas  ON concerto_arranjos(arranjo_id)
    WHERE data_execucao IS NOT NULL;
