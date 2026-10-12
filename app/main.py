"""
Portal — Ponto de entrada da aplicação FastAPI.
"""

import json
import logging
import os
import secrets
from pathlib import Path
from contextlib import asynccontextmanager

import redis as redis_lib

from fastapi import FastAPI, Request, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.exception_handlers import http_exception_handler as default_http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import bcrypt

from app.database import engine, Base, get_db
from app.models import Musician, MemberRole, RoleType, User, UserRole, InstrumentoBase, Patrimonio, TipoItem, StatusPatrimonio, Configuracao, Obra, Arranjo, Concerto, ConcertoArranjo, ReleaseNote
from app.seeds import INSTRUMENTS_SEED
from app.dependencies import make_ctx, get_lang, set_lang_cookie
from app.limiter import limiter
from app.spa_modules import path_served_by_spa, spa_dist_ready, SPA_DIR
from app.routers import musicians, auth, users, instrumentos, settings as settings_router
from app.routers import patrimonio as patrimonio_router
from app.routers import search as search_router
from app.routers import acervo as acervo_router
from app.routers import programacao as programacao_router
from app.routers import release_notes as release_notes_router

logger = logging.getLogger("uvicorn.error")

UPLOAD_DIR = Path(os.path.abspath("uploads"))

# S-01/S-02: SECRET_KEY obrigatória; falha explícita se ausente em produção
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = "change-me-in-production-use-32-random-chars"
    logger.warning("SECRET_KEY não definida — usando valor padrão inseguro. Defina a variável de ambiente SECRET_KEY em produção.")

# S-05: https_only controlado por variável de ambiente
HTTPS_ONLY = os.getenv("HTTPS_ONLY", "0") == "1"

PUBLIC_PATHS = {"/login", "/forgot-password", "/healthz", "/readyz"}
PUBLIC_PREFIXES = (
    "/static",
    "/uploads",
    "/favicon",
    "/assets",  # SPA Vite build
    "/instrumentos",
    "/reset-password",
    "/patrimonio/qr",
    "/patrimonio/scan",
    "/acervo/calendario.ics",
    "/acervo/programacao/ical",
    "/acervo/programacao/acesso",
    "/api/",
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
)


class AuthMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "GET")

        if path.startswith("/api/") or path in {"/api/docs", "/api/redoc", "/api/openapi.json"}:
            await self.app(scope, receive, send)
            return
        if path == "/m" or path.startswith("/m/"):
            await self.app(scope, receive, send)
            return
        if path.startswith("/assets"):
            await self.app(scope, receive, send)
            return
        # Módulos SPA: JWT no cliente (sem cookie de sessão)
        if method == "GET" and path_served_by_spa(path):
            await self.app(scope, receive, send)
            return
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            await self.app(scope, receive, send)
            return

        session = scope.get("session", {})
        if not session.get("user"):
            response = RedirectResponse(url="/login", status_code=302)
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


class SpaModulesMiddleware:
    """Devolve o shell React para GET em paths de SPA_MODULES."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method") != "GET":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path.startswith("/assets/"):
            await self.app(scope, receive, send)
            return
        if path_served_by_spa(path):
            index = SPA_DIR / "index.html"
            if index.is_file():
                response = FileResponse(index)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


class ProtectScoreUploadsMiddleware:
    """
    Impede download anônimo de partituras em /uploads/obras/*.
    Mantém logos/fotos públicas e download via token/API FileResponse.
    Staff autenticado (sessão) continua podendo visualizar no painel.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path.startswith("/uploads/obras/"):
            session = scope.get("session") or {}
            if not session.get("user"):
                from starlette.responses import JSONResponse
                resp = JSONResponse(
                    {"detail": "Acesso a partituras requer autenticação."},
                    status_code=401,
                )
                await resp(scope, receive, send)
                return
        await self.app(scope, receive, send)


# ──────────────────────────────────────────────────────────────
# i18n
# ──────────────────────────────────────────────────────────────

def load_translations():
    t = {}
    for lang in ("pt", "en", "es"):
        with open(Path(f"app/i18n/{lang}.json"), "r", encoding="utf-8") as f:
            t[lang] = json.load(f)
    return t


# ──────────────────────────────────────────────────────────────
# Startup helpers
# ──────────────────────────────────────────────────────────────

def create_default_admin(db: Session):
    """S-02: usa ADMIN_PASSWORD do ambiente; usa 'admin' como senha padrão se não definida."""
    if db.query(User).count() == 0:
        admin_password = os.getenv("ADMIN_PASSWORD", "").strip()
        if not admin_password:
            admin_password = "admin"
            logger.warning("=" * 60)
            logger.warning("  Portal — Administrador padrão criado com senha padrão:")
            logger.warning("  Usuário: admin  |  Senha: admin")
            logger.warning("  ATENÇÃO: Altere a senha imediatamente após o primeiro login!")
            logger.warning("  Defina ADMIN_PASSWORD no ambiente para controlar a senha.")
            logger.warning("=" * 60)
        else:
            logger.warning("  Portal — Administrador padrão criado via ADMIN_PASSWORD.")

        admin = User(
            username="admin",
            email="admin@localhost",
            password_hash=bcrypt.hashpw(admin_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            role=UserRole.admin,
        )
        db.add(admin)
        db.commit()


def populate_instruments(db: Session):
    """Insere instrumentos do seed que ainda não existem (upsert por nome)."""
    existing = {row[0] for row in db.query(InstrumentoBase.nome).all()}
    added = 0
    for nome, categoria in INSTRUMENTS_SEED:
        if nome not in existing:
            db.add(InstrumentoBase(nome=nome, categoria=categoria))
            added += 1
    if added:
        db.commit()
        logger.info(f"[Portal] {added} instrumento(s) adicionado(s) à tabela instrumentos_base.")


def load_branding(upload_dir: Path) -> dict:
    """Carrega configurações de branding do arquivo JSON."""
    branding_file = upload_dir / "branding.json"
    if branding_file.exists():
        try:
            return json.loads(branding_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def load_smtp_settings(upload_dir: Path) -> dict:
    """Carrega configurações de SMTP do arquivo JSON (sem expor a senha em logs)."""
    f = upload_dir / "app_settings.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def connect_redis() -> redis_lib.Redis | None:
    """Conecta ao Redis; retorna None se indisponível (graceful degradation)."""
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        client = redis_lib.from_url(url, decode_responses=True, socket_connect_timeout=2)
        client.ping()
        logger.info("[Portal] Redis conectado: %s", url)
        return client
    except Exception as exc:
        logger.warning("[Portal] Redis indisponível (%s) — cache desativado.", exc)
        return None


def ensure_patrimonio_sequences(db: Session):
    """Cria as sequences de identificador de patrimônio se ainda não existirem (idempotente)."""
    from sqlalchemy import text
    sequences = [
        ("seq_patrimonio_ins", "Instrumento"),
        ("seq_patrimonio_mov", "Movel"),
        ("seq_patrimonio_ele", "Eletronico"),
        ("seq_patrimonio_par", "Partitura"),
        ("seq_patrimonio_dec", "Decoracao"),
        ("seq_patrimonio_out", "Outros"),
    ]
    for seq_name, tipo_value in sequences:
        exists = db.execute(
            text("SELECT 1 FROM pg_sequences WHERE sequencename = :s"),
            {"s": seq_name},
        ).scalar()
        if not exists:
            cnt = db.execute(
                text("SELECT GREATEST(COUNT(*), 0) FROM patrimonio WHERE tipo_item = :t"),
                {"t": tipo_value},
            ).scalar() or 0
            db.execute(text(f"CREATE SEQUENCE {seq_name} START WITH {cnt + 1}"))
            logger.info(f"[Portal] Sequence {seq_name} criada (start={cnt + 1}).")
    db.commit()


def ensure_schema_upgrades(db: Session) -> None:
    """Garante colunas/índices em DBs já existentes (create_all não altera colunas).

    Deve rodar ANTES de qualquer query ORM em `users` / `configuracoes`.
    """
    from sqlalchemy import text

    for ddl in (
        "ALTER TABLE configuracoes ADD COLUMN IF NOT EXISTS idioma VARCHAR(5) NOT NULL DEFAULT 'pt'",
        "ALTER TABLE configuracoes ADD COLUMN IF NOT EXISTS audit_retention_days INTEGER NOT NULL DEFAULT 90",
        "ALTER TABLE configuracoes ADD COLUMN IF NOT EXISTS pwa_enabled BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS musician_id INTEGER NULL REFERENCES musicians(id) ON DELETE SET NULL",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_musician_id ON users (musician_id) WHERE musician_id IS NOT NULL",
        """
        CREATE TABLE IF NOT EXISTS api_refresh_tokens (
          id          SERIAL PRIMARY KEY,
          user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          token_hash  VARCHAR(64) NOT NULL UNIQUE,
          expires_at  TIMESTAMPTZ NOT NULL,
          revoked_at  TIMESTAMPTZ NULL,
          created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          user_agent  VARCHAR(255) NULL,
          client      VARCHAR(40) NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_api_refresh_tokens_user_id ON api_refresh_tokens (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_api_refresh_tokens_expires_at ON api_refresh_tokens (expires_at)",
        """
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
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_release_notes_released_at ON release_notes (released_at)",
        "CREATE INDEX IF NOT EXISTS ix_release_notes_version ON release_notes (version)",
        "ALTER TABLE patrimonio ADD COLUMN IF NOT EXISTS qr_payload VARCHAR(512)",
        "ALTER TABLE patrimonio ADD COLUMN IF NOT EXISTS barcode_value VARCHAR(64)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_patrimonio_barcode_value ON patrimonio (barcode_value) WHERE barcode_value IS NOT NULL",
        "CREATE INDEX IF NOT EXISTS ix_patrimonio_qr_payload ON patrimonio (qr_payload)",
        """
        CREATE TABLE IF NOT EXISTS whatsapp_grupos (
          id            SERIAL PRIMARY KEY,
          codigo        VARCHAR(64)  NOT NULL UNIQUE,
          nome          VARCHAR(120) NOT NULL,
          tipo          VARCHAR(32)  NOT NULL DEFAULT 'orquestra',
          whatsapp_url  VARCHAR(500) NULL,
          telefone      VARCHAR(20)  NULL,
          ordem         INTEGER      NOT NULL DEFAULT 0,
          ativo         BOOLEAN      NOT NULL DEFAULT TRUE,
          created_at    TIMESTAMP    NULL DEFAULT NOW(),
          updated_at    TIMESTAMP    NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_whatsapp_grupos_codigo ON whatsapp_grupos (codigo)",
        "CREATE INDEX IF NOT EXISTS ix_whatsapp_grupos_tipo ON whatsapp_grupos (tipo)",
    ):
        try:
            db.execute(text(ddl))
            db.commit()
        except Exception:
            db.rollback()

    try:
        from app.routers.whatsapp_pwa import ensure_whatsapp_grupos
        ensure_whatsapp_grupos(db)
    except Exception as exc:
        logger.warning("[Portal] Seed WhatsApp grupos: %s", exc)
        db.rollback()

    # Backfill códigos de inventário (itens legados)
    try:
        db.execute(text("""
            UPDATE patrimonio
            SET
              qr_payload = COALESCE(qr_payload, '/patrimonio/scan/' || id::text),
              barcode_value = COALESCE(barcode_value, identificador_interno)
            WHERE qr_payload IS NULL OR barcode_value IS NULL
        """))
        db.commit()
    except Exception:
        db.rollback()

    # Espelha QR/barcode em patrimonio_etiqueta (reativa antes de inserir — uq_etiqueta_valor)
    try:
        db.execute(text("""
            UPDATE patrimonio_etiqueta e
            SET patrimonio_id = p.id, ativo = TRUE
            FROM patrimonio p
            WHERE e.tipo = 'qr'::etiqueta_tipo_enum
              AND e.valor = p.id::text
              AND e.ativo = FALSE
        """))
        db.execute(text("""
            UPDATE patrimonio_etiqueta e
            SET patrimonio_id = p.id, ativo = TRUE
            FROM patrimonio p
            WHERE e.tipo = 'barcode_1d'::etiqueta_tipo_enum
              AND e.valor = p.barcode_value
              AND e.ativo = FALSE
              AND p.barcode_value IS NOT NULL
        """))
        db.execute(text("""
            INSERT INTO patrimonio_etiqueta (patrimonio_id, tipo, valor, ativo, created_at)
            SELECT p.id, 'qr'::etiqueta_tipo_enum, p.id::text, TRUE, NOW()
            FROM patrimonio p
            WHERE NOT EXISTS (
              SELECT 1 FROM patrimonio_etiqueta e
              WHERE e.tipo = 'qr' AND e.valor = p.id::text
            )
        """))
        db.execute(text("""
            INSERT INTO patrimonio_etiqueta (patrimonio_id, tipo, valor, ativo, created_at)
            SELECT p.id, 'barcode_1d'::etiqueta_tipo_enum, p.barcode_value, TRUE, NOW()
            FROM patrimonio p
            WHERE p.barcode_value IS NOT NULL
              AND NOT EXISTS (
                SELECT 1 FROM patrimonio_etiqueta e
                WHERE e.tipo = 'barcode_1d' AND e.valor = p.barcode_value
              )
        """))
        db.commit()
    except Exception:
        db.rollback()


def ensure_footer_config(db: Session) -> dict:
    """Garante que a linha singleton de configurações exista e retorna seus dados."""
    cfg = db.query(Configuracao).filter(Configuracao.id == 1).first()
    if cfg is None:
        cfg = Configuracao(
            id=1,
            nome_institucional="",
            endereco="",
            link_estatuto="",
            link_repositorio="",
            idioma="pt",
            audit_retention_days=90,
            pwa_enabled=False,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg.to_dict()


# ──────────────────────────────────────────────────────────────
# Lifespan
# ──────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    from app.audit import purge_expired_logs

    UPLOAD_DIR.mkdir(exist_ok=True)
    Base.metadata.create_all(bind=engine)
    app.state.translations   = load_translations()
    app.state.branding       = load_branding(UPLOAD_DIR)
    app.state.smtp_settings  = load_smtp_settings(UPLOAD_DIR)
    app.state.redis          = connect_redis()
    from app.version import get_version
    app.state.app_version = get_version()

    db = next(get_db())
    try:
        ensure_schema_upgrades(db)
        create_default_admin(db)
        populate_instruments(db)
        ensure_patrimonio_sequences(db)
        footer = ensure_footer_config(db)
        app.state.footer_config = footer
        app.state.app_lang = footer.get("idioma", "pt")
        release_notes_router.sync_code_version(db, app.state.app_version)
        app.state.app_version = get_version()
    finally:
        db.close()

    try:
        deleted = purge_expired_logs()
        if deleted:
            logger.info("[Portal] Auditoria: expurgo inicial removeu %s registro(s).", deleted)
    except Exception:
        logger.exception("[Portal] Expurgo inicial de auditoria falhou")

    stop_purge = asyncio.Event()

    async def _purge_loop():
        while not stop_purge.is_set():
            try:
                await asyncio.wait_for(stop_purge.wait(), timeout=3600)
                break
            except asyncio.TimeoutError:
                try:
                    n = await asyncio.to_thread(purge_expired_logs)
                    if n:
                        logger.info("[Portal] Auditoria: expurgo removeu %s registro(s).", n)
                except Exception:
                    logger.exception("[Portal] Expurgo periódico de auditoria falhou")

    purge_task = asyncio.create_task(_purge_loop())

    yield

    stop_purge.set()
    purge_task.cancel()
    try:
        await purge_task
    except asyncio.CancelledError:
        pass

    if app.state.redis:
        app.state.redis.close()


# ──────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Orchestra Portal — Portal do Membro",
    description=(
        "Portal web e API mobile (`/api/v1`) para músicos (Android/iOS).\n\n"
        "**Mobile:** use `Authorization: Bearer <access_token>`, "
        "HTTPS em produção, armazene refresh token no Keystore/Keychain, "
        "renove com `POST /api/v1/auth/refresh` (rotação)."
    ),
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# S-04: rate limiter
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """HTML amigável no login/forgot; fallback SlowAPI para o restante."""
    path = request.url.path.rstrip("/") or "/"
    if request.method == "POST" and path in {"/login", "/forgot-password"}:
        from fastapi.templating import Jinja2Templates
        from app.dependencies import make_ctx, get_lang, set_lang_cookie

        lang = get_lang(request)
        translations = getattr(request.app.state, "translations", {}) or {}
        t = translations.get(lang) or translations.get("pt") or {}
        error_msg = t.get("login_rate_limited") or str(exc.detail)

        username = ""
        if path == "/login":
            try:
                form = await request.form()
                username = (form.get("username") or "").strip()
            except Exception:
                username = ""

        templates = Jinja2Templates(directory="templates")
        if path == "/login":
            ctx = make_ctx(request, {"error": error_msg, "username": username})
            template_name = "auth/login.html"
        else:
            ctx = make_ctx(request, {"sent": False, "error": error_msg})
            template_name = "auth/forgot_password.html"

        resp = templates.TemplateResponse(template_name, ctx, status_code=429)
        return set_lang_cookie(resp, lang)

    return await _rate_limit_exceeded_handler(request, exc)


# D-03: no portal web, 403 (ex.: require_admin) redireciona ao início.
# Na API mobile, 403 deve permanecer JSON (Android/iOS).
@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
    path = request.url.path
    if path.startswith("/api/"):
        return await default_http_exception_handler(request, exc)
    if exc.status_code == 403:
        return RedirectResponse(url="/", status_code=302)
    return await default_http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """P0: 500 controlado — não vaza stack na UI; loga com request_id."""
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import HTMLResponse, JSONResponse
    from app.observability import get_request_id

    # Deixa handlers específicos cuidarem destes casos
    if isinstance(exc, StarletteHTTPException):
        return await custom_http_exception_handler(request, exc)
    if isinstance(exc, RateLimitExceeded):
        return await rate_limit_handler(request, exc)
    if isinstance(exc, RequestValidationError):
        from fastapi.exception_handlers import request_validation_exception_handler
        return await request_validation_exception_handler(request, exc)

    rid = get_request_id(request)
    logger.exception("unhandled_error request_id=%s path=%s", rid, request.url.path)

    accept = (request.headers.get("accept") or "").lower()
    if "application/json" in accept:
        return JSONResponse(
            status_code=500,
            content={"detail": "Erro interno do servidor.", "request_id": rid},
            headers={"X-Request-ID": rid},
        )
    html = (
        "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>"
        "<title>Erro</title></head><body style='font-family:sans-serif;padding:40px;'>"
        "<h1>Algo deu errado</h1>"
        "<p>Ocorreu um erro interno. Tente novamente em instantes.</p>"
        f"<p style='color:#666;font-size:13px;'>Código de referência: <code>{rid}</code></p>"
        "<p><a href='/'>Voltar ao início</a></p></body></html>"
    )
    return HTMLResponse(content=html, status_code=500, headers={"X-Request-ID": rid})


# Ordem (último add = mais externo):
#   RequestContext → ProtectUploads → Session → Auth → Audit → rotas
from app.observability import RequestContextMiddleware
from app.audit_middleware import AuditMiddleware

_BOOT_NONCE = secrets.token_hex(8)

app.add_middleware(AuditMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(SpaModulesMiddleware)
app.add_middleware(ProtectScoreUploadsMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=f"{SECRET_KEY}:{_BOOT_NONCE}",
    session_cookie="portal_session",
    max_age=60 * 60 * 8,
    https_only=HTTPS_ONLY,
    same_site="lax",
)
app.add_middleware(RequestContextMiddleware)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

templates = Jinja2Templates(directory="templates")

# Hybrid: Jinja sempre montado; SPA_MODULES intercepta GET via SpaModulesMiddleware
app.include_router(auth.router)
app.include_router(musicians.router)
app.include_router(users.router)
app.include_router(instrumentos.router)
app.include_router(settings_router.router)
app.include_router(patrimonio_router.router)
app.include_router(search_router.router)
app.include_router(acervo_router.router)
app.include_router(programacao_router.router)
app.include_router(programacao_router.compat_router)

from app.routers import whatsapp_pwa as whatsapp_pwa_router
app.include_router(whatsapp_pwa_router.router)


@app.get("/acervo/calendario.ics")
def calendario_ics_alias():
    """Atalho legado → feed iCal da programação."""
    return RedirectResponse(url="/acervo/programacao/ical/feed.ics", status_code=302)


app.include_router(release_notes_router.router)
app.include_router(release_notes_router.admin_router)

from app.api.router import api_router
app.include_router(api_router)

from app.routers import pwa as pwa_router
app.include_router(pwa_router.router)


# ──────────────────────────────────────────────────────────────
# Health probes (P0) — públicos, sem auth
# ──────────────────────────────────────────────────────────────

@app.get("/healthz")
async def healthz():
    """Liveness: processo respondendo."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(request: Request):
    """Readiness: DB obrigatório; Redis opcional (degraded se ausente)."""
    from fastapi.responses import JSONResponse
    from sqlalchemy import text

    services = {}
    overall = "ok"

    try:
        db = next(get_db())
        try:
            db.execute(text("SELECT 1"))
            services["database"] = {"status": "ok"}
        finally:
            db.close()
    except Exception as exc:
        services["database"] = {"status": "error", "detail": str(exc)[:120]}
        overall = "error"

    r = getattr(request.app.state, "redis", None)
    if r is None:
        services["redis"] = {"status": "degraded", "detail": "não conectado"}
        if overall == "ok":
            overall = "degraded"
    else:
        try:
            r.ping()
            services["redis"] = {"status": "ok"}
        except Exception as exc:
            services["redis"] = {"status": "degraded", "detail": str(exc)[:120]}
            if overall == "ok":
                overall = "degraded"

    body = {"status": overall, "services": services}
    code = 200 if overall != "error" else 503
    return JSONResponse(body, status_code=code)



# Assets da SPA (quando build existe)
if spa_dist_ready():
    assets_dir = SPA_DIR / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="spa_assets")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    from datetime import date, datetime, timedelta, timezone
    from sqlalchemy import extract

    active_q = db.query(Musician).filter(Musician.is_active == True)  # noqa: E712
    inv_q = db.query(Patrimonio).filter(Patrimonio.status != StatusPatrimonio.Baixa)
    agora = datetime.now(timezone.utc)
    em_7d = agora + timedelta(days=7)
    mes_atual = date.today().month

    _MESES = {
        "pt": ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
               "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"],
        "en": ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"],
        "es": ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
               "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
    }
    lang = get_lang(request)
    mes_nome = _MESES.get(lang, _MESES["pt"])[mes_atual - 1]

    stats = {
        "active": active_q.count(),
        "inv_emprestados": inv_q.filter(Patrimonio.status == StatusPatrimonio.Emprestado).count(),
        "inv_manutencao": inv_q.filter(Patrimonio.status == StatusPatrimonio.Manutencao).count(),
        "eventos_7d": (
            db.query(Concerto)
            .filter(Concerto.data_inicio >= agora, Concerto.data_inicio < em_7d)
            .count()
        ),
        "inv_instrumentos": inv_q.filter(Patrimonio.tipo_item == TipoItem.Instrumento).count(),
        "inv_moveis": inv_q.filter(Patrimonio.tipo_item == TipoItem.Movel).count(),
        "inv_eletronicos": inv_q.filter(Patrimonio.tipo_item == TipoItem.Eletronico).count(),
        "inv_partituras": inv_q.filter(Patrimonio.tipo_item == TipoItem.Partitura).count(),
        "inv_decoracoes": inv_q.filter(Patrimonio.tipo_item == TipoItem.Decoracao).count(),
    }

    proximos_eventos = (
        db.query(Concerto)
        .filter(Concerto.data_inicio >= agora)
        .order_by(Concerto.data_inicio.asc())
        .limit(5)
        .all()
    )

    atencao_itens = (
        inv_q.filter(
            Patrimonio.status.in_([StatusPatrimonio.Emprestado, StatusPatrimonio.Manutencao])
        )
        .order_by(Patrimonio.status.desc())
        .limit(5)
        .all()
    )

    aniversariantes = (
        db.query(Musician)
        .filter(
            Musician.is_active == True,  # noqa: E712
            extract("month", Musician.birth_date) == mes_atual,
        )
        .order_by(extract("day", Musician.birth_date))
        .limit(8)
        .all()
    )

    ctx = make_ctx(request, {
        "stats": stats,
        "proximos_eventos": proximos_eventos,
        "atencao_itens": atencao_itens,
        "aniversariantes": aniversariantes,
        "mes_nome": mes_nome,
        "mes_atual": mes_atual,
    })
    resp = templates.TemplateResponse("index.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])

@app.get("/design-system", response_class=HTMLResponse)
async def design_system_page(request: Request):
    from app.dependencies import get_current_user, is_admin
    user = get_current_user(request)
    if not is_admin(user):
        return RedirectResponse(url="/", status_code=302)
    ctx = make_ctx(request)
    resp = templates.TemplateResponse("design_system.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])

@app.get("/set-lang/{lang}")
async def set_lang(lang: str, request: Request):
    """Legado: redireciona. Idioma só muda em Configurações (admin)."""
    from app.dependencies import is_admin, get_current_user
    if not is_admin(get_current_user(request)):
        return RedirectResponse(url="/", status_code=302)
    return RedirectResponse(url="/settings/?section=geral", status_code=302)
