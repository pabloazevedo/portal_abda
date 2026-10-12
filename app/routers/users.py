"""Usuários de sistema (admin, maestro, arquivista, secretaria).

Contas de App/PWA para músicos e coralistas são gerenciadas no cadastro de Membros.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import bcrypt

from app.database import get_db
from app.models import User, UserRole
from app.app_access import SYSTEM_ROLES
from app.dependencies import make_ctx, get_lang, set_lang_cookie, is_admin, get_current_user
from app.audit import audit_from_request

router = APIRouter(prefix="/users")
templates = Jinja2Templates(directory="templates")

_SYSTEM_ROLE_VALUES = {r.value for r in SYSTEM_ROLES}


def _hash(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _require_admin(request: Request) -> bool:
    return is_admin(get_current_user(request))


def _parse_system_role(raw: str) -> UserRole | None:
    try:
        role = UserRole(raw)
    except ValueError:
        return None
    if role not in SYSTEM_ROLES:
        return None
    return role


@router.get("/", response_class=HTMLResponse)
async def list_users(request: Request, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/", status_code=302)
    users = (
        db.query(User)
        .filter(User.role.in_(list(SYSTEM_ROLES)))
        .order_by(User.username)
        .all()
    )
    ctx = make_ctx(request, {"users": users})
    resp = templates.TemplateResponse("users/list.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.get("/new", response_class=HTMLResponse)
async def new_user_form(request: Request, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/", status_code=302)
    ctx = make_ctx(request, {
        "user_obj": None,
        "errors": {},
        "form_data": {"role": "secretaria"},
    })
    resp = templates.TemplateResponse("users/form.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.post("/new", response_class=HTMLResponse)
async def create_user(
    request: Request,
    db: Session = Depends(get_db),
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    role: str = Form(...),
):
    if not _require_admin(request):
        return RedirectResponse(url="/", status_code=302)
    lang = get_lang(request)
    t = request.app.state.translations[lang]

    errors = {}
    parsed_role = _parse_system_role(role)
    form_data = {"username": username, "email": email, "role": role}

    if parsed_role is None:
        errors["role"] = t.get(
            "error_system_role_required",
            "Selecione um papel de sistema (admin, maestro, arquivista ou secretaria).",
        )
    if len(password) < 6:
        errors["password"] = t["error_password_min"]
    elif password != confirm_password:
        errors["confirm_password"] = t["error_password_mismatch"]
    if db.query(User).filter(User.username == username.strip()).first():
        errors["username"] = t["error_username_exists"]
    if db.query(User).filter(User.email == email.strip().lower()).first():
        errors["email"] = t["error_email_exists"]

    if errors:
        ctx = make_ctx(request, {
            "user_obj": None,
            "errors": errors,
            "form_data": form_data,
        })
        resp = templates.TemplateResponse("users/form.html", ctx)
        return set_lang_cookie(resp, lang)

    user = User(
        username=username.strip(),
        email=email.strip().lower(),
        password_hash=_hash(password),
        role=parsed_role,
        musician_id=None,
    )
    db.add(user)
    db.commit()
    audit_from_request(
        request,
        action="users.create",
        entity_type="user",
        entity_id=str(user.id),
        summary=f"Usuário de sistema criado: {user.username} ({user.role.value})",
    )
    resp = RedirectResponse(url="/users/", status_code=303)
    return set_lang_cookie(resp, lang)


@router.get("/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_form(request: Request, user_id: int, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/", status_code=302)
    user_obj = db.query(User).filter(User.id == user_id).first()
    if not user_obj:
        raise HTTPException(status_code=404)
    if user_obj.role not in SYSTEM_ROLES:
        # Contas de app ficam no cadastro de Membros
        return RedirectResponse(url="/users/", status_code=302)
    ctx = make_ctx(request, {
        "user_obj": user_obj,
        "errors": {},
        "form_data": {},
    })
    resp = templates.TemplateResponse("users/form.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.post("/{user_id}/edit", response_class=HTMLResponse)
async def update_user(
    request: Request,
    user_id: int,
    db: Session = Depends(get_db),
    username: str = Form(...),
    email: str = Form(...),
    role: str = Form(...),
    password: Optional[str] = Form(None),
    confirm_password: Optional[str] = Form(None),
):
    if not _require_admin(request):
        return RedirectResponse(url="/", status_code=302)
    lang = get_lang(request)
    t = request.app.state.translations[lang]
    user_obj = db.query(User).filter(User.id == user_id).first()
    if not user_obj:
        raise HTTPException(status_code=404)
    if user_obj.role not in SYSTEM_ROLES:
        return RedirectResponse(url="/users/", status_code=302)

    parsed_role = _parse_system_role(role)
    errors = {}
    form_data = {"username": username, "email": email, "role": role}

    if parsed_role is None:
        errors["role"] = t.get(
            "error_system_role_required",
            "Selecione um papel de sistema (admin, maestro, arquivista ou secretaria).",
        )
    if password:
        if len(password) < 6:
            errors["password"] = t["error_password_min"]
        elif password != confirm_password:
            errors["confirm_password"] = t["error_password_mismatch"]
    if db.query(User).filter(User.username == username.strip(), User.id != user_id).first():
        errors["username"] = t["error_username_exists"]
    if db.query(User).filter(User.email == email.strip().lower(), User.id != user_id).first():
        errors["email"] = t["error_email_exists"]

    if errors:
        ctx = make_ctx(request, {
            "user_obj": user_obj,
            "errors": errors,
            "form_data": form_data,
        })
        resp = templates.TemplateResponse("users/form.html", ctx)
        return set_lang_cookie(resp, lang)

    user_obj.username = username.strip()
    user_obj.email = email.strip().lower()
    user_obj.role = parsed_role
    if password:
        user_obj.password_hash = _hash(password)
    db.commit()

    current = get_current_user(request)
    if current and current["id"] == user_id:
        request.session["user"]["username"] = user_obj.username
        request.session["user"]["role"] = user_obj.role.value

    audit_from_request(
        request,
        action="users.update",
        entity_type="user",
        entity_id=str(user_id),
        summary=f"Usuário de sistema atualizado: {user_obj.username} ({user_obj.role.value})",
    )

    resp = RedirectResponse(url="/users/", status_code=303)
    return set_lang_cookie(resp, lang)


@router.post("/{user_id}/toggle-status")
async def toggle_user_status(request: Request, user_id: int, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/", status_code=302)
    lang = request.cookies.get("lang", "pt")
    current = get_current_user(request)
    if current and current["id"] == user_id:
        resp = RedirectResponse(url="/users/", status_code=303)
        return set_lang_cookie(resp, lang)
    user_obj = db.query(User).filter(User.id == user_id).first()
    if not user_obj:
        raise HTTPException(status_code=404)
    user_obj.is_active = not user_obj.is_active
    db.commit()
    resp = RedirectResponse(url="/users/", status_code=303)
    return set_lang_cookie(resp, lang)


@router.post("/{user_id}/delete")
async def delete_user(request: Request, user_id: int, db: Session = Depends(get_db)):
    if not _require_admin(request):
        return RedirectResponse(url="/", status_code=302)
    lang = request.cookies.get("lang", "pt")
    current = get_current_user(request)
    if current and current["id"] == user_id:
        resp = RedirectResponse(url="/users/", status_code=303)
        return set_lang_cookie(resp, lang)
    user_obj = db.query(User).filter(User.id == user_id).first()
    if not user_obj:
        raise HTTPException(status_code=404)
    db.delete(user_obj)
    db.commit()
    resp = RedirectResponse(url="/users/", status_code=303)
    return set_lang_cookie(resp, lang)
