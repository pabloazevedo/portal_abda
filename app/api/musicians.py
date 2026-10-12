"""API v1 — CRUD de membros."""
from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import require_api_manage_members, require_system_user
from app.app_access import get_app_user, grant_app_access, has_app_access, revoke_app_access
from app.database import get_db
from app.models import InstrumentoBase, MemberRole, Musician, RoleType, User, VoiceType

router = APIRouter(prefix="/musicians", tags=["Musicians"])


def _serialize(m: Musician, db: Session | None = None) -> dict:
    data = {
        "id": m.id,
        "first_name": m.first_name,
        "last_name": m.last_name,
        "full_name": m.full_name,
        "apelido": m.apelido,
        "email": m.email,
        "celular": m.celular,
        "telefone": m.telefone,
        "birth_date": m.birth_date.isoformat() if m.birth_date else None,
        "photo": m.photo,
        "is_active": m.is_active,
        "age": m.age if m.birth_date else None,
        "roles": [
            {
                "role_type": r.role_type.value,
                "label": r.label,
                "maestro_order": r.maestro_order,
                "voice_type": r.voice_type.value if r.voice_type else None,
            }
            for r in (m.roles or [])
        ],
        "instruments": [
            {"id": i.id, "nome": i.nome, "categoria": i.categoria}
            for i in (m.instruments or [])
        ],
        "role_labels": m.role_labels,
        "instrument_names": m.instrument_names,
    }
    if db is not None:
        data["has_app_access"] = has_app_access(db, m.id)
        app_user = get_app_user(db, m.id)
        data["app_username"] = app_user.username if app_user else None
    return data


def _apply_roles(
    db: Session,
    musician: Musician,
    roles: List[str],
    maestro_order: Optional[int],
    voice_type: Optional[str],
):
    db.query(MemberRole).filter(MemberRole.musician_id == musician.id).delete()
    for raw in roles:
        try:
            rt = RoleType(raw)
        except ValueError:
            continue
        mo = maestro_order if rt == RoleType.maestro else None
        vt = None
        if rt == RoleType.cantor and voice_type:
            try:
                vt = VoiceType(voice_type)
            except ValueError:
                vt = None
        db.add(MemberRole(musician_id=musician.id, role_type=rt, maestro_order=mo, voice_type=vt))


def _apply_instruments(db: Session, musician: Musician, instrumento_ids: List[int]):
    instruments = (
        db.query(InstrumentoBase).filter(InstrumentoBase.id.in_(instrumento_ids)).all()
        if instrumento_ids
        else []
    )
    musician.instruments = instruments


class MusicianCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    apelido: Optional[str] = None
    email: str = Field(..., min_length=3, max_length=150)
    celular: str = Field(..., min_length=8, max_length=20)
    telefone: Optional[str] = None
    birth_date: date
    is_active: bool = True
    roles: List[str] = []
    maestro_order: Optional[int] = None
    voice_type: Optional[str] = None
    instrumento_ids: List[int] = []
    app_password: Optional[str] = None


class MusicianUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    apelido: Optional[str] = None
    email: Optional[str] = None
    celular: Optional[str] = None
    telefone: Optional[str] = None
    birth_date: Optional[date] = None
    is_active: Optional[bool] = None
    roles: Optional[List[str]] = None
    maestro_order: Optional[int] = None
    voice_type: Optional[str] = None
    instrumento_ids: Optional[List[int]] = None
    app_password: Optional[str] = None
    grant_app: Optional[bool] = None


@router.get("")
async def list_musicians(
    q: str = "",
    role: str = "",
    status: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    query = db.query(Musician)
    if q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Musician.first_name.ilike(term),
                Musician.last_name.ilike(term),
                Musician.email.ilike(term),
                Musician.apelido.ilike(term),
            )
        )
    if status == "active":
        query = query.filter(Musician.is_active == True)  # noqa: E712
    elif status == "inactive":
        query = query.filter(Musician.is_active == False)  # noqa: E712
    if role:
        try:
            rt = RoleType(role)
            query = query.join(MemberRole).filter(MemberRole.role_type == rt)
        except ValueError:
            pass

    total = query.count()
    items = (
        query.order_by(Musician.first_name, Musician.last_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_serialize(m, db) for m in items],
    }


@router.get("/instruments")
async def list_instruments(
    q: str = "",
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    query = db.query(InstrumentoBase).filter(InstrumentoBase.ativo == True)  # noqa: E712
    if q.strip():
        query = query.filter(InstrumentoBase.nome.ilike(f"%{q.strip()}%"))
    items = query.order_by(InstrumentoBase.categoria, InstrumentoBase.nome).limit(50).all()
    return [{"id": i.id, "nome": i.nome, "categoria": i.categoria} for i in items]




@router.get("/organogram")
async def organogram(
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    """Estrutura do organograma para a SPA."""
    musicians = db.query(Musician).filter(Musician.is_active == True).all()  # noqa: E712
    nodes: list[dict] = [
        {"id": "root", "pid": None, "type": "root", "name": "Orquestra & Coral", "role": "Organização"},
        {"id": "grp_maestro", "pid": "root", "type": "group", "name": "Direção Artística", "role": "Maestros"},
        {"id": "grp_chefe", "pid": "root", "type": "group", "name": "Chefia de Naipes", "role": "Chefes"},
        {"id": "grp_musico", "pid": "root", "type": "group", "name": "Orquestra", "role": "Músicos", "member_count": 0},
        {"id": "grp_coral", "pid": "root", "type": "group", "name": "Coral", "role": "Coralistas", "member_count": 0},
        {"id": "grp_suporte", "pid": "root", "type": "group", "name": "Suporte", "role": "Staff"},
    ]
    by_id = {n["id"]: n for n in nodes}
    _pid = {
        "maestro": "grp_maestro",
        "chefe_naipe": "grp_chefe",
        "arranjador": "grp_suporte",
        "compositor": "grp_suporte",
        "arquivista": "grp_suporte",
    }
    for m in musicians:
        for role in m.roles or []:
            rt = role.role_type.value
            if rt == "musico":
                by_id["grp_musico"]["member_count"] = by_id["grp_musico"].get("member_count", 0) + 1
                continue
            if rt == "cantor":
                by_id["grp_coral"]["member_count"] = by_id["grp_coral"].get("member_count", 0) + 1
                continue
            pid = _pid.get(rt)
            if not pid:
                continue
            nodes.append({
                "id": f"m{m.id}_{rt}",
                "pid": pid,
                "type": "member",
                "name": m.full_name,
                "role": role.label,
                "musician_id": m.id,
                "photo": f"/uploads/{m.photo}" if m.photo else None,
                "profile_url": f"/musicians/{m.id}",
            })
    return {"nodes": nodes}


@router.post("/{musician_id}/photo")
async def upload_photo(
    musician_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_members),
    file: UploadFile = File(...),
):
    from app.routers.musicians import save_photo, delete_photo
    m = db.query(Musician).filter(Musician.id == musician_id).first()
    if not m:
        raise HTTPException(404, "Membro não encontrado.")
    old = m.photo
    filename = await save_photo(file)
    if not filename:
        raise HTTPException(400, "Arquivo de imagem inválido.")
    m.photo = filename
    if old:
        delete_photo(old)
    db.commit()
    return _serialize(m, db)


@router.post("/{musician_id}/revoke-app")
async def revoke_app(
    musician_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_members),
):
    from app.app_access import revoke_app_access
    if not db.query(Musician).filter(Musician.id == musician_id).first():
        raise HTTPException(404, "Membro não encontrado.")
    revoke_app_access(db, musician_id)
    db.commit()
    return {"ok": True}

@router.get("/{musician_id}")
async def get_musician(
    musician_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_system_user),
):
    m = db.query(Musician).filter(Musician.id == musician_id).first()
    if not m:
        raise HTTPException(404, "Membro não encontrado.")
    return _serialize(m, db)


@router.post("", status_code=201)
async def create_musician(
    body: MusicianCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_members),
):
    if db.query(Musician).filter(Musician.email == str(body.email).lower()).first():
        raise HTTPException(400, "Email já cadastrado.")
    m = Musician(
        first_name=body.first_name.strip(),
        last_name=body.last_name.strip(),
        apelido=(body.apelido or "").strip() or None,
        email=str(body.email).lower(),
        celular=body.celular.strip(),
        telefone=(body.telefone or "").strip() or None,
        birth_date=body.birth_date,
        is_active=body.is_active,
    )
    db.add(m)
    db.flush()
    _apply_roles(db, m, body.roles, body.maestro_order, body.voice_type)
    _apply_instruments(db, m, body.instrumento_ids)
    if body.app_password:
        grant_app_access(db, m, body.app_password)
    db.commit()
    db.refresh(m)
    return _serialize(m, db)


@router.put("/{musician_id}")
async def update_musician(
    musician_id: int,
    body: MusicianUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_members),
):
    m = db.query(Musician).filter(Musician.id == musician_id).first()
    if not m:
        raise HTTPException(404, "Membro não encontrado.")
    data = body.model_dump(exclude_unset=True)
    for field in ("first_name", "last_name", "apelido", "celular", "telefone", "birth_date", "is_active"):
        if field in data:
            setattr(m, field, data[field])
    if "email" in data and data["email"]:
        m.email = str(data["email"]).lower()
    if "roles" in data and data["roles"] is not None:
        _apply_roles(db, m, data["roles"], body.maestro_order, body.voice_type)
    if "instrumento_ids" in data and data["instrumento_ids"] is not None:
        _apply_instruments(db, m, data["instrumento_ids"])
    if body.grant_app is False:
        revoke_app_access(db, musician_id)
    elif body.app_password:
        grant_app_access(db, m, body.app_password)
    db.commit()
    db.refresh(m)
    return _serialize(m, db)


@router.post("/{musician_id}/toggle-status")
async def toggle_status(
    musician_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_members),
):
    m = db.query(Musician).filter(Musician.id == musician_id).first()
    if not m:
        raise HTTPException(404, "Membro não encontrado.")
    m.is_active = not m.is_active
    db.commit()
    return {"id": m.id, "is_active": m.is_active}


@router.delete("/{musician_id}")
async def delete_musician(
    musician_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_api_manage_members),
):
    m = db.query(Musician).filter(Musician.id == musician_id).first()
    if not m:
        raise HTTPException(404, "Membro não encontrado.")
    revoke_app_access(db, musician_id)
    db.delete(m)
    db.commit()
    return {"ok": True}
