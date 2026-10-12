"""
Portal — Router de Membros (músicos e cantores).
Suporta múltiplos papéis (RoleType) e múltiplos instrumentos (M2M).
"""

import logging
import os
import uuid
from pathlib import Path
from datetime import date
from typing import Optional, List

from fastapi import APIRouter, Depends, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_, extract

from app.database import get_db
from app.models import Musician, MemberRole, RoleType, VoiceType, InstrumentoBase, Patrimonio, PatrimonioEmprestimo, StatusPatrimonio
from app.dependencies import make_ctx, get_lang, set_lang_cookie, is_admin, get_current_user, require_admin, require_manage_members
from app.utils import detect_image_type  # D-02: magic bytes centralizados
from app.app_access import (
    get_app_user,
    has_app_access,
    grant_app_access,
    revoke_app_access,
    set_app_password,
)

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/musicians")
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = Path(os.path.abspath("uploads"))
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

_MESES = {
    "pt": ["Janeiro","Fevereiro","Março","Abril","Maio","Junho","Julho","Agosto","Setembro","Outubro","Novembro","Dezembro"],
    "en": ["January","February","March","April","May","June","July","August","September","October","November","December"],
    "es": ["Enero","Febrero","Marzo","Abril","Mayo","Junio","Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"],
}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

async def save_photo(file: Optional[UploadFile]) -> Optional[str]:
    if file is None:
        return None
    if not file.filename:
        return None
    ext = Path(file.filename).suffix.lower()
    logger.info(f"save_photo: filename={file.filename!r}  ext={ext!r}  content_type={file.content_type!r}")
    if ext not in ALLOWED_EXTENSIONS:
        logger.warning(f"save_photo: extension {ext!r} not allowed")
        return None
    contents = await file.read()
    logger.info(f"save_photo: {len(contents)} bytes read")
    if len(contents) == 0:
        return None
    if len(contents) > MAX_FILE_SIZE:
        logger.warning(f"save_photo: file too large ({len(contents)} bytes)")
        return None
    detected = detect_image_type(contents)  # D-02: usa utilitário centralizado
    if detected is None:
        logger.warning(f"save_photo: magic bytes não reconhecidos, upload rejeitado")
        return None
    safe_ext = detected if detected != ".jpeg" else ".jpg"
    filename = f"{uuid.uuid4()}{safe_ext}"
    dest = UPLOAD_DIR / filename
    dest.write_bytes(contents)
    logger.info(f"save_photo: saved → {dest}")
    return filename


def delete_photo(filename: Optional[str]):
    if filename:
        path = UPLOAD_DIR / filename
        if path.exists():
            path.unlink()


def validate_celular(celular: str) -> tuple[bool, str]:
    """Celular brasileiro: DDD (2) + 9 + 8 dígitos = 11 total."""
    clean = ''.join(filter(str.isdigit, celular))
    if len(clean) != 11:
        return False, "Celular deve ter 11 dígitos com DDD (ex: 11 98888-8888)"
    if clean[2] != '9':
        return False, "O primeiro dígito após o DDD deve ser 9 (ex: 11 98888-8888)"
    return True, ""


def validate_telefone(telefone: str) -> tuple[bool, str]:
    """Telefone fixo brasileiro opcional: DDD (2) + 8 dígitos = 10 total."""
    if not telefone or not telefone.strip():
        return True, ""
    clean = ''.join(filter(str.isdigit, telefone))
    if len(clean) != 10:
        return False, "Telefone fixo deve ter 10 dígitos com DDD (ex: 11 3333-8888)"
    return True, ""


def _build_stats(db: Session) -> dict:
    active_q = db.query(Musician).filter(Musician.is_active == True)
    return {
        "total":    db.query(Musician).count(),
        "active":   active_q.count(),
        "musicos":  active_q.filter(
            Musician.roles.any(MemberRole.role_type == RoleType.musico)
        ).count(),
        "cantores": active_q.filter(
            Musician.roles.any(MemberRole.role_type == RoleType.cantor)
        ).count(),
        "maestros": active_q.filter(
            Musician.roles.any(MemberRole.role_type == RoleType.maestro)
        ).count(),
    }


def _apply_roles(db: Session, musician: Musician, roles: List[str], maestro_order: Optional[str], voice_type: Optional[str]):
    """Remove papéis antigos e insere os novos."""
    logger.info(f"_apply_roles: musician_id={musician.id}, roles={roles}, maestro_order={maestro_order}, voice_type={voice_type}")
    deleted = db.query(MemberRole).filter(MemberRole.musician_id == musician.id).delete()
    logger.info(f"_apply_roles: deleted {deleted} existing roles")

    for role_str in roles:
        try:
            rt = RoleType(role_str)
        except ValueError:
            logger.warning(f"_apply_roles: invalid role {role_str}")
            continue
        mo = None
        vt = None
        if rt == RoleType.maestro and maestro_order:
            try:
                mo = int(maestro_order)
            except (ValueError, TypeError):
                mo = None
        if rt == RoleType.cantor and voice_type:
            try:
                vt = VoiceType(voice_type)
            except ValueError:
                logger.warning(f"_apply_roles: invalid voice_type {voice_type}")
        mr = MemberRole(musician_id=musician.id, role_type=rt, maestro_order=mo, voice_type=vt)
        db.add(mr)
        logger.info(f"_apply_roles: added {rt.value} (maestro_order={mo}, voice_type={vt})")
    logger.info(f"_apply_roles: done")


def _apply_instruments(db: Session, musician: Musician, instrumento_ids: List[str]):
    """Substitui instrumentos do membro pelos novos ids."""
    musician.instruments.clear()
    for raw in instrumento_ids:
        try:
            iid = int(raw)
        except (ValueError, TypeError):
            continue
        inst = db.get(InstrumentoBase, iid)
        if inst:
            musician.instruments.append(inst)


# ──────────────────────────────────────────────────────────────
# LIST
# ──────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def list_musicians(
    request: Request,
    db: Session = Depends(get_db),
    search: str = "",
    role_filter: str = "",
    status: str = "active",
    page: int = 1,
):
    query = db.query(Musician)

    if status == "active":
        query = query.filter(Musician.is_active == True)
    elif status == "inactive":
        query = query.filter(Musician.is_active == False)

    valid_roles = {r.value for r in RoleType}
    if role_filter and role_filter in valid_roles:
        query = query.filter(
            Musician.roles.any(MemberRole.role_type == RoleType(role_filter))
        )

    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                Musician.first_name.ilike(term),
                Musician.last_name.ilike(term),
                Musician.email.ilike(term),
                Musician.apelido.ilike(term),
            )
        )

    total = query.count()
    per_page = 25
    pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, pages))
    musicians = (
        query.order_by(Musician.first_name)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )

    lang = get_lang(request)
    mes_atual = date.today().month
    mes_nome  = _MESES.get(lang, _MESES["pt"])[mes_atual - 1]
    aniversariantes = (
        db.query(Musician)
        .filter(
            Musician.is_active == True,
            extract("month", Musician.birth_date) == mes_atual,
        )
        .order_by(extract("day", Musician.birth_date))
        .all()
    )

    ctx = make_ctx(request, {
        "musicians": musicians,
        "search": search,
        "role_filter": role_filter,
        "status": status,
        "page": page,
        "pages": pages,
        "total": total,
        "stats": _build_stats(db),
        "role_types": list(RoleType),
        "aniversariantes": aniversariantes,
        "mes_nome": mes_nome,
        "mes_atual": mes_atual,
    })
    resp = templates.TemplateResponse("musicians/list.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


# ──────────────────────────────────────────────────────────────
# NEW — GET  (deve vir ANTES de /{musician_id} para não ser capturada pelo param)
# ──────────────────────────────────────────────────────────────

@router.get("/new", response_class=HTMLResponse)
async def new_musician_form(
    request: Request,
    _user: dict = Depends(require_manage_members),
):
    ctx = make_ctx(request, {
        "musician": None,
        "selected_role_values": [],
        "selected_instrumento_ids": [],
        "selected_instruments": [],
        "maestro_order_value": None,
        "voice_type_value": None,
        "errors": {},
        "form_data": {},
        "role_types": list(RoleType),
        "voice_types": list(VoiceType),
        "app_access": False,
        "app_user": None,
    })
    resp = templates.TemplateResponse("musicians/form.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


# ──────────────────────────────────────────────────────────────
# NEW — POST
# ──────────────────────────────────────────────────────────────

@router.get("/organogram", response_class=HTMLResponse)
async def organogram_view(request: Request):
    ctx = make_ctx(request, {})
    resp = templates.TemplateResponse("musicians/organogram.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.get("/organogram/data", response_class=JSONResponse)
async def organogram_data(
    request: Request,
    db: Session = Depends(get_db),
):
    """Retorna a estrutura hierárquica completa como JSON flat (id/pid) para o organograma dinâmico."""
    musicians = db.query(Musician).filter(Musician.is_active == True).all()

    # ── Nós fixos: raiz + grupos de papel ─────────────────────────────────────
    nodes: list[dict] = [
        {
            "id": "root", "pid": None, "type": "root",
            "name": "Orquestra & Coral",
            "role": "Organização",
            "icon": "bi-building", "color": "#4f6ef7",
            "photo": None, "apelido": None,
            "instruments": [], "maestro_order": None,
            "voice_type": None, "profile_url": None,
        },
        # ── Grupos principais ──────────────────────────────────────────────────
        {"id": "grp_maestro",   "pid": "root",        "type": "group", "group_role": "maestro",
         "name": "Direção Artística", "role": "Maestros / Maestrinas",
         "icon": "bi-music-note-beamed", "color": "#1e3a5f"},
        {"id": "grp_chefe",     "pid": "root",        "type": "group", "group_role": "chefe_naipe",
         "name": "Chefia de Naipes",  "role": "Chefes de Naipe",
         "icon": "bi-award-fill",      "color": "#7c3aed"},
        {"id": "grp_musico",    "pid": "root",        "type": "group", "group_role": "musico",
         "name": "Orquestra",          "role": "Músicos",
         "icon": "bi-music-note-list", "color": "#065f46",
         "member_count": 0,
         "list_url": "/musicians/?role_filter=musico&status=active"},
        {"id": "grp_coral",     "pid": "root",        "type": "group", "group_role": "coral",
         "name": "Coral",              "role": "Coralistas",
         "icon": "bi-mic-fill",        "color": "#be185d",
         "member_count": 0,
         "list_url": "/musicians/?role_filter=cantor&status=active"},
        {"id": "grp_suporte",   "pid": "root",        "type": "group", "group_role": "suporte",
         "name": "Suporte Artístico",  "role": "Staff",
         "icon": "bi-people-fill",     "color": "#374151"},
        # ── Sub-grupos do Suporte ──────────────────────────────────────────────
        {"id": "grp_arranjador",  "pid": "grp_suporte", "type": "subgroup", "group_role": "arranjador",
         "name": "Arranjadores", "role": "", "icon": "bi-file-music",   "color": "#7c3aed"},
        {"id": "grp_compositor",  "pid": "grp_suporte", "type": "subgroup", "group_role": "compositor",
         "name": "Compositores", "role": "", "icon": "bi-pen",           "color": "#0d9488"},
        {"id": "grp_arquivista",  "pid": "grp_suporte", "type": "subgroup", "group_role": "arquivista",
         "name": "Arquivistas",  "role": "", "icon": "bi-folder2-open",  "color": "#b45309"},
    ]

    # Índices dos grupos agregados (Orquestra / Coral) — só contagem + link
    by_id = {n["id"]: n for n in nodes}
    seen_musico: set[int] = set()
    seen_coral: set[int] = set()

    # ── Nós de membros (exceto orquestra/coral: listas dedicadas) ─────────────
    _pid_by_role = {
        "maestro":    "grp_maestro",
        "chefe_naipe": "grp_chefe",
        "arranjador": "grp_arranjador",
        "compositor": "grp_compositor",
        "arquivista": "grp_arquivista",
    }
    _label_by_role = {
        "chefe_naipe": "Chefe de Naipe",
        "arranjador":  "Arranjador",
        "compositor":  "Compositor",
        "arquivista":  "Arquivista",
    }

    for m in musicians:
        instruments = [i.nome for i in (m.instruments or [])]
        photo = f"/uploads/{m.photo}" if m.photo else None

        for role in m.roles:
            rt = role.role_type.value

            if rt == "musico":
                if m.id not in seen_musico:
                    seen_musico.add(m.id)
                    by_id["grp_musico"]["member_count"] += 1
                continue
            if rt == "cantor":
                if m.id not in seen_coral:
                    seen_coral.add(m.id)
                    by_id["grp_coral"]["member_count"] += 1
                continue

            if rt not in _pid_by_role:
                continue

            pid = _pid_by_role[rt]
            if rt == "maestro":
                role_label = (
                    f"{role.maestro_order}º Maestro/Maestrina"
                    if role.maestro_order else "Maestro/Maestrina"
                )
            else:
                role_label = _label_by_role[rt]

            nodes.append({
                "id":            f"m_{m.id}_{rt}",
                "pid":           pid,
                "type":          rt,
                "name":          m.full_name,
                "apelido":       m.apelido,
                "role":          role_label,
                "photo":         photo,
                "instruments":   instruments,
                "maestro_order": role.maestro_order,
                "voice_type":    role.voice_type.value if role.voice_type else None,
                "profile_url":   f"/musicians/{m.id}",
                "icon":          None,
                "color":         None,
            })

    return nodes


@router.post("/new", response_class=HTMLResponse)
async def create_musician(
    request: Request,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_manage_members),
    first_name: str = Form(...),
    last_name: str = Form(...),
    apelido: Optional[str] = Form(None),
    celular: str = Form(...),
    telefone: Optional[str] = Form(None),
    email: str = Form(...),
    birth_date: str = Form(...),
    roles: List[str] = Form(default=[]),
    instrumento_ids: List[str] = Form(default=[]),
    maestro_order: Optional[str] = Form(None),
    voice_type: Optional[str] = Form(None),
    photo: UploadFile = File(None),
    app_access: Optional[str] = Form(None),
    app_password: Optional[str] = Form(None),
    app_password_confirm: Optional[str] = Form(None),
):
    lang = get_lang(request)
    t = request.app.state.translations[lang]
    want_app = bool(app_access)
    errors: dict = {}
    form_data = {
        "first_name": first_name, "last_name": last_name,
        "apelido": apelido or "",
        "celular": celular, "telefone": telefone or "",
        "email": email, "birth_date": birth_date,
    }

    cel_valid, cel_error = validate_celular(celular)
    if not cel_valid:
        errors["celular"] = cel_error
    tel_valid, tel_error = validate_telefone(telefone or "")
    if not tel_valid:
        errors["telefone"] = tel_error

    # Validate roles
    valid_roles = [r.value for r in RoleType]
    logger.info(f"create_musician: received roles={roles}, valid_roles={valid_roles}")
    roles = [r for r in roles if r in valid_roles]
    logger.info(f"create_musician: filtered roles={roles}")
    if not roles:
        errors["roles"] = t.get("error_roles_required", "Selecione ao menos um papel")
        logger.warning(f"create_musician: no roles selected")
    if "maestro" in roles and not maestro_order:
        errors["maestro_order"] = t.get("error_maestro_order_required", "Informe a ordem do maestro")
    if "cantor" in roles and not voice_type:
        errors["voice_type"] = t.get("error_voice_type_required", "Informe o tipo de voz para coralistas")

    # Validate email
    if db.query(Musician).filter(Musician.email == email.strip().lower()).first():
        errors["email"] = t["error_email_exists"]

    # Validate birth date
    bd = None
    try:
        bd = date.fromisoformat(birth_date)
    except ValueError:
        errors["birth_date"] = t["error_invalid_date"]

    if want_app:
        pwd = (app_password or "").strip()
        conf = (app_password_confirm or "").strip()
        if len(pwd) < 6:
            errors["app_password"] = t.get("error_password_min", "Senha deve ter ao menos 6 caracteres.")
        elif pwd != conf:
            errors["app_password_confirm"] = t.get("error_password_mismatch", "As senhas não coincidem.")

    # Load instruments for tag re-display
    selected_instruments = []
    for raw in instrumento_ids:
        try:
            inst = db.get(InstrumentoBase, int(raw))
            if inst:
                selected_instruments.append(inst)
        except (ValueError, TypeError):
            pass

    if errors:
        ctx = make_ctx(request, {
            "musician": None,
            "selected_role_values": roles,
            "selected_instrumento_ids": [str(i.id) for i in selected_instruments],
            "selected_instruments": selected_instruments,
            "maestro_order_value": maestro_order,
            "voice_type_value": voice_type,
            "errors": errors,
            "form_data": form_data,
            "role_types": list(RoleType),
            "voice_types": list(VoiceType),
            "app_access": want_app,
            "app_user": None,
        })
        resp = templates.TemplateResponse("musicians/form.html", ctx)
        return set_lang_cookie(resp, lang)

    photo_filename = await save_photo(photo) if photo else None

    musician = Musician(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        apelido=(apelido.strip() if apelido and apelido.strip() else None),
        celular=celular.strip(),
        telefone=(telefone.strip() if telefone and telefone.strip() else None),
        email=email.strip().lower(),
        birth_date=bd,
        photo=photo_filename,
    )
    db.add(musician)
    db.flush()  # Gera musician.id

    _apply_roles(db, musician, roles, maestro_order, voice_type)
    _apply_instruments(db, musician, instrumento_ids)

    if want_app:
        try:
            grant_app_access(db, musician, (app_password or "").strip())
        except ValueError as exc:
            db.rollback()
            errors["app_access"] = str(exc)
            ctx = make_ctx(request, {
                "musician": None,
                "selected_role_values": roles,
                "selected_instrumento_ids": [str(i.id) for i in selected_instruments],
                "selected_instruments": selected_instruments,
                "maestro_order_value": maestro_order,
                "voice_type_value": voice_type,
                "errors": errors,
                "form_data": form_data,
                "role_types": list(RoleType),
                "voice_types": list(VoiceType),
                "app_access": True,
                "app_user": None,
            })
            resp = templates.TemplateResponse("musicians/form.html", ctx)
            return set_lang_cookie(resp, lang)

    db.commit()
    db.refresh(musician)
    resp = RedirectResponse(url=f"/musicians/{musician.id}", status_code=303)
    return set_lang_cookie(resp, lang)


# ──────────────────────────────────────────────────────────────
# DETAIL — GET /musicians/{id}  (após /new para evitar conflito de rota)
# ──────────────────────────────────────────────────────────────

@router.get("/{musician_id}", response_class=HTMLResponse)
async def musician_detail(
    request: Request,
    musician_id: int,
    db: Session = Depends(get_db),
):
    musician = db.get(Musician, musician_id)
    if musician is None:
        raise HTTPException(status_code=404, detail="Membro não encontrado.")

    emprestimos = (
        db.query(PatrimonioEmprestimo)
        .filter(
            PatrimonioEmprestimo.musician_id == musician_id,
            PatrimonioEmprestimo.data_devolucao == None,
        )
        .all()
    )

    app_user = get_app_user(db, musician_id)
    ctx = make_ctx(request, {
        "musician": musician,
        "emprestimos": emprestimos,
        "app_user": app_user,
        "has_app_access": bool(app_user and app_user.is_active),
    })
    resp = templates.TemplateResponse("musicians/detail.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


# ──────────────────────────────────────────────────────────────
# EDIT — GET
# ──────────────────────────────────────────────────────────────

@router.get("/{musician_id}/edit", response_class=HTMLResponse)
async def edit_musician_form(
    request: Request,
    musician_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_manage_members),
):
    musician = db.query(Musician).filter(Musician.id == musician_id).first()
    if not musician:
        raise HTTPException(status_code=404)

    existing_roles = [mr.role_type.value for mr in musician.roles]
    maestro_role = next((mr for mr in musician.roles if mr.role_type == RoleType.maestro), None)
    cantor_role = next((mr for mr in musician.roles if mr.role_type == RoleType.cantor), None)

    # Equipamentos em posse (empréstimos ativos)
    equipamentos_ativos = (
        db.query(PatrimonioEmprestimo)
        .filter(
            PatrimonioEmprestimo.musician_id == musician_id,
            PatrimonioEmprestimo.data_devolucao == None,
        )
        .all()
    )
    # Itens disponíveis para vincular ao músico
    patrimonio_disponivel = (
        db.query(Patrimonio)
        .filter(Patrimonio.status == StatusPatrimonio.Disponivel)
        .order_by(Patrimonio.tipo_item, Patrimonio.identificador_interno)
        .all()
    )

    ctx = make_ctx(request, {
        "musician": musician,
        "selected_role_values": existing_roles,
        "selected_instrumento_ids": [str(i.id) for i in musician.instruments],
        "selected_instruments": list(musician.instruments),
        "maestro_order_value": maestro_role.maestro_order if maestro_role else None,
        "voice_type_value": cantor_role.voice_type.value if cantor_role and cantor_role.voice_type else None,
        "errors": {},
        "form_data": {},
        "role_types": list(RoleType),
        "voice_types": list(VoiceType),
        "equipamentos_ativos": equipamentos_ativos,
        "patrimonio_disponivel": patrimonio_disponivel,
        "app_user": get_app_user(db, musician_id),
        "app_access": has_app_access(db, musician_id),
    })
    resp = templates.TemplateResponse("musicians/form.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


# ──────────────────────────────────────────────────────────────
# EDIT — POST
# ──────────────────────────────────────────────────────────────

@router.post("/{musician_id}/edit", response_class=HTMLResponse)
async def update_musician(
    request: Request,
    musician_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_manage_members),
    first_name: str = Form(...),
    last_name: str = Form(...),
    apelido: Optional[str] = Form(None),
    celular: str = Form(...),
    telefone: Optional[str] = Form(None),
    email: str = Form(...),
    birth_date: str = Form(...),
    roles: List[str] = Form(default=[]),
    instrumento_ids: List[str] = Form(default=[]),
    maestro_order: Optional[str] = Form(None),
    voice_type: Optional[str] = Form(None),
    photo: UploadFile = File(None),
    remove_photo: Optional[str] = Form(None),
    app_access: Optional[str] = Form(None),
    app_password: Optional[str] = Form(None),
    app_password_confirm: Optional[str] = Form(None),
):
    lang = get_lang(request)
    t = request.app.state.translations[lang]
    musician = db.query(Musician).filter(Musician.id == musician_id).first()
    if not musician:
        raise HTTPException(status_code=404)

    want_app = bool(app_access)
    had_app = has_app_access(db, musician_id)
    admin = is_admin(get_current_user(request))

    errors: dict = {}
    form_data = {
        "first_name": first_name, "last_name": last_name,
        "apelido": apelido or "",
        "celular": celular, "telefone": telefone or "",
        "email": email, "birth_date": birth_date,
    }

    cel_valid, cel_error = validate_celular(celular)
    if not cel_valid:
        errors["celular"] = cel_error
    tel_valid, tel_error = validate_telefone(telefone or "")
    if not tel_valid:
        errors["telefone"] = tel_error

    valid_roles = [r.value for r in RoleType]
    roles = [r for r in roles if r in valid_roles]
    if not roles:
        errors["roles"] = t.get("error_roles_required", "Selecione ao menos um papel")
    if "maestro" in roles and not maestro_order:
        errors["maestro_order"] = t.get("error_maestro_order_required", "Informe a ordem do maestro")
    if "cantor" in roles and not voice_type:
        errors["voice_type"] = t.get("error_voice_type_required", "Informe o tipo de voz para coralistas")

    if (
        db.query(Musician)
        .filter(Musician.email == email.strip().lower(), Musician.id != musician_id)
        .first()
    ):
        errors["email"] = t["error_email_exists"]

    bd = None
    try:
        bd = date.fromisoformat(birth_date)
    except ValueError:
        errors["birth_date"] = t["error_invalid_date"]

    pwd = (app_password or "").strip()
    conf = (app_password_confirm or "").strip()
    if want_app and not had_app:
        if len(pwd) < 6:
            errors["app_password"] = t.get("error_password_min", "Senha deve ter ao menos 6 caracteres.")
        elif pwd != conf:
            errors["app_password_confirm"] = t.get("error_password_mismatch", "As senhas não coincidem.")
    elif want_app and had_app and pwd:
        if len(pwd) < 6:
            errors["app_password"] = t.get("error_password_min", "Senha deve ter ao menos 6 caracteres.")
        elif pwd != conf:
            errors["app_password_confirm"] = t.get("error_password_mismatch", "As senhas não coincidem.")
    elif not want_app and had_app and not admin:
        errors["app_access"] = t.get(
            "error_app_revoke_admin_only",
            "Somente administradores podem remover o acesso ao App.",
        )

    selected_instruments = []
    for raw in instrumento_ids:
        try:
            inst = db.get(InstrumentoBase, int(raw))
            if inst:
                selected_instruments.append(inst)
        except (ValueError, TypeError):
            pass

    def _err_ctx():
        return make_ctx(request, {
            "musician": musician,
            "selected_role_values": roles,
            "selected_instrumento_ids": [str(i.id) for i in selected_instruments],
            "selected_instruments": selected_instruments,
            "maestro_order_value": maestro_order,
            "voice_type_value": voice_type,
            "errors": errors,
            "form_data": form_data,
            "role_types": list(RoleType),
            "voice_types": list(VoiceType),
            "app_access": want_app,
            "app_user": get_app_user(db, musician_id),
        })

    if errors:
        resp = templates.TemplateResponse("musicians/form.html", _err_ctx())
        return set_lang_cookie(resp, lang)

    if photo and photo.filename:
        new_photo = await save_photo(photo)
        if new_photo:
            delete_photo(musician.photo)
            musician.photo = new_photo
    elif remove_photo == "1":
        delete_photo(musician.photo)
        musician.photo = None

    musician.first_name = first_name.strip()
    musician.last_name  = last_name.strip()
    musician.apelido    = (apelido.strip() if apelido and apelido.strip() else None)
    musician.celular    = celular.strip()
    musician.telefone   = (telefone.strip() if telefone and telefone.strip() else None)
    musician.email      = email.strip().lower()
    musician.birth_date = bd

    db.flush()
    _apply_roles(db, musician, roles, maestro_order, voice_type)
    _apply_instruments(db, musician, instrumento_ids)

    try:
        if want_app and not had_app:
            grant_app_access(db, musician, pwd)
        elif want_app and had_app and pwd:
            set_app_password(db, musician_id, pwd)
        elif not want_app and had_app and admin:
            revoke_app_access(db, musician_id)
    except ValueError as exc:
        errors["app_access"] = str(exc)
        resp = templates.TemplateResponse("musicians/form.html", _err_ctx())
        return set_lang_cookie(resp, lang)

    db.commit()
    resp = RedirectResponse(url=f"/musicians/{musician_id}", status_code=303)
    return set_lang_cookie(resp, lang)


# ──────────────────────────────────────────────────────────────
# TOGGLE STATUS / DELETE / APP ACCESS
# ──────────────────────────────────────────────────────────────

@router.post("/{musician_id}/revoke-app")
async def revoke_musician_app_access(
    request: Request,
    musician_id: int,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    lang = get_lang(request)
    musician = db.query(Musician).filter(Musician.id == musician_id).first()
    if not musician:
        raise HTTPException(status_code=404)
    revoke_app_access(db, musician_id)
    db.commit()
    resp = RedirectResponse(url=f"/musicians/{musician_id}", status_code=303)
    return set_lang_cookie(resp, lang)


@router.post("/{musician_id}/toggle-status")
async def toggle_status(
    request: Request,
    musician_id: int,
    db: Session = Depends(get_db),
    _user: dict = Depends(require_manage_members),
):
    lang = request.cookies.get("lang", "pt")
    musician = db.query(Musician).filter(Musician.id == musician_id).first()
    if not musician:
        raise HTTPException(status_code=404)
    musician.is_active = not musician.is_active
    db.commit()
    resp = RedirectResponse(url="/musicians/", status_code=303)
    return set_lang_cookie(resp, lang)


@router.post("/{musician_id}/delete")
async def delete_musician(
    request: Request,
    musician_id: int,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    lang = request.cookies.get("lang", "pt")
    musician = db.query(Musician).filter(Musician.id == musician_id).first()
    if not musician:
        raise HTTPException(status_code=404)
    revoke_app_access(db, musician_id)
    delete_photo(musician.photo)
    db.delete(musician)
    db.commit()
    resp = RedirectResponse(url="/musicians/", status_code=303)
    return set_lang_cookie(resp, lang)

