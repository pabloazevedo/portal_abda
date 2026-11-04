import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from app.templating import Templates
from sqlalchemy.orm import Session
import bcrypt

from app.database import get_db
from app.models import User, PasswordResetToken
from app.dependencies import make_ctx, get_lang, set_lang_cookie
from app.email_utils import send_password_reset
from app.limiter import limiter

logger = logging.getLogger("uvicorn.error")

router = APIRouter()
templates = Templates(directory="templates")

TOKEN_EXPIRY_HOURS = 1


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ──────────────────────────────────────────────────────────────
# Login / Logout
# ──────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("user"):
        return RedirectResponse(url="/", status_code=302)
    ctx = make_ctx(request, {"error": None, "username": ""})
    resp = templates.TemplateResponse("auth/login.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.post("/login", response_class=HTMLResponse)
@limiter.limit("5/minute")  # S-04: proteção contra força bruta
async def login(
    request: Request,
    db: Session = Depends(get_db),
    username: str = Form(...),
    password: str = Form(...),
):
    lang = get_lang(request)
    t = request.app.state.translations[lang]
    user = db.query(User).filter(User.username == username.strip()).first()

    error = None
    if not user or not verify_password(password, user.password_hash):
        error = t["login_error"]
    elif not user.is_active:
        error = t["login_inactive"]

    if error:
        from app.audit import audit_from_request
        audit_from_request(
            request,
            action="auth.login_failed",
            entity_type="user",
            summary=f"Falha de login para usuário '{username.strip()}'",
        )
        ctx = make_ctx(request, {"error": error, "username": username})
        resp = templates.TemplateResponse("auth/login.html", ctx)
        return set_lang_cookie(resp, lang)

    request.session["user"] = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
    }
    from app.audit import audit_from_request
    audit_from_request(
        request,
        action="auth.login",
        entity_type="user",
        entity_id=str(user.id),
        summary=f"Login de {user.username}",
    )
    resp = RedirectResponse(url="/", status_code=303)
    return set_lang_cookie(resp, lang)


@router.post("/logout")
async def logout(request: Request):
    from app.audit import audit_from_request
    user = request.session.get("user") or {}
    audit_from_request(
        request,
        action="auth.logout",
        entity_type="user",
        entity_id=str(user.get("id") or ""),
        summary=f"Logout de {user.get('username') or 'desconhecido'}",
    )
    lang = request.cookies.get("lang", "pt")
    request.session.clear()
    resp = RedirectResponse(url="/login", status_code=303)
    return set_lang_cookie(resp, lang)


# ──────────────────────────────────────────────────────────────
# Esqueci a senha
# ──────────────────────────────────────────────────────────────

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    ctx = make_ctx(request, {"sent": False, "error": None})
    resp = templates.TemplateResponse("auth/forgot_password.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.post("/forgot-password", response_class=HTMLResponse)
@limiter.limit("5/minute")  # S-04: proteção contra enumeração via timing
async def forgot_password_submit(
    request: Request,
    db: Session = Depends(get_db),
    email: str = Form(...),
):
    lang = get_lang(request)

    # Sempre mostra a mesma mensagem independente de o email existir
    # (evita enumeração de usuários)
    user = db.query(User).filter(
        User.email == email.strip().lower(),
        User.is_active == True,
    ).first()

    if user:
        # Invalida tokens anteriores não usados deste usuário
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at == None,
        ).delete()

        raw_token  = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRY_HOURS)

        db.add(PasswordResetToken(
            user_id    = user.id,
            token_hash = token_hash,
            expires_at = expires_at,
        ))
        db.commit()

        # Envia email em background (não bloqueia a resposta)
        try:
            smtp_cfg = getattr(request.app.state, "smtp_settings", {})
            send_password_reset(user.email, raw_token, settings=smtp_cfg)
        except Exception as exc:
            logger.error(f"[Portal] Erro ao enviar email de redefinição: {exc}")

    ctx = make_ctx(request, {"sent": True, "error": None})
    resp = templates.TemplateResponse("auth/forgot_password.html", ctx)
    return set_lang_cookie(resp, lang)


# ──────────────────────────────────────────────────────────────
# Redefinir senha
# ──────────────────────────────────────────────────────────────

def _get_valid_token(db: Session, raw_token: str) -> PasswordResetToken | None:
    token_hash = _hash_token(raw_token)
    return db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == token_hash,
        PasswordResetToken.expires_at  > datetime.now(timezone.utc),
        PasswordResetToken.used_at     == None,
    ).first()


@router.get("/reset-password/{token}", response_class=HTMLResponse)
async def reset_password_page(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
):
    record = _get_valid_token(db, token)
    if not record:
        ctx = make_ctx(request, {"valid": False, "token": token, "error": None, "success": False})
        resp = templates.TemplateResponse("auth/reset_password.html", ctx)
        return set_lang_cookie(resp, ctx["lang"])

    ctx = make_ctx(request, {"valid": True, "token": token, "error": None, "success": False})
    resp = templates.TemplateResponse("auth/reset_password.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.post("/reset-password/{token}", response_class=HTMLResponse)
async def reset_password_submit(
    request: Request,
    token: str,
    db: Session = Depends(get_db),
    password: str = Form(...),
    confirm_password: str = Form(...),
):
    lang = get_lang(request)

    record = _get_valid_token(db, token)
    if not record:
        ctx = make_ctx(request, {"valid": False, "token": token, "error": None, "success": False})
        resp = templates.TemplateResponse("auth/reset_password.html", ctx)
        return set_lang_cookie(resp, lang)

    error = None
    if len(password) < 8:
        error = "A senha deve ter no mínimo 8 caracteres."
    elif password != confirm_password:
        error = "As senhas não coincidem."

    if error:
        ctx = make_ctx(request, {"valid": True, "token": token, "error": error, "success": False})
        resp = templates.TemplateResponse("auth/reset_password.html", ctx)
        return set_lang_cookie(resp, lang)

    # Atualiza senha e marca token como usado
    record.user.password_hash = hash_password(password)
    record.used_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(f"[Portal] Senha redefinida para user_id={record.user_id}")

    ctx = make_ctx(request, {"valid": True, "token": token, "error": None, "success": True})
    resp = templates.TemplateResponse("auth/reset_password.html", ctx)
    return set_lang_cookie(resp, lang)
