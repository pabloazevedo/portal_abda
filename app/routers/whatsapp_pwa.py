"""
Portal — Envio do link do Site mobile / PWA via WhatsApp
para grupos de naipes da orquestra e do coral.
"""

from __future__ import annotations

import json
import logging
import os
import re
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import make_ctx, set_lang_cookie, require_admin, get_lang
from app.models import Configuracao, WhatsAppGrupo

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/settings/whatsapp-pwa")
templates = Jinja2Templates(directory="templates")

# Grupos padrão (naipes orquestra + coral STAB)
DEFAULT_GRUPOS: list[tuple[str, str, str, int]] = [
    ("orch_geral", "Orquestra — Geral", "orquestra", 10),
    ("orch_vl1", "1º Violinos", "orquestra", 20),
    ("orch_vl2", "2º Violinos", "orquestra", 30),
    ("orch_va", "Violas", "orquestra", 40),
    ("orch_vc", "Violoncelos", "orquestra", 50),
    ("orch_cb", "Contrabaixos", "orquestra", 60),
    ("orch_madeiras", "Madeiras (Fl / Ob / Cl / Fg)", "orquestra", 70),
    ("orch_metais", "Metais (Tp / Cor / Trb / Tuba)", "orquestra", 80),
    ("orch_perc", "Percussão / Tímpanos", "orquestra", 90),
    ("orch_outros", "Harpa / Piano / Teclado", "orquestra", 100),
    ("coral_geral", "Coral STAB — Geral", "coral", 200),
    ("coral_soprano", "Coral — Sopranos", "coral", 210),
    ("coral_alto", "Coral — Contraltos", "coral", 220),
    ("coral_tenor", "Coral — Tenores", "coral", 230),
    ("coral_baixo", "Coral — Baixos", "coral", 240),
]


def ensure_whatsapp_grupos(db: Session) -> None:
    """Cria tabela (via create_all/schema) e seeds idempotentes."""
    existing = {g.codigo for g in db.query(WhatsAppGrupo.codigo).all()}
    added = 0
    for codigo, nome, tipo, ordem in DEFAULT_GRUPOS:
        if codigo in existing:
            continue
        db.add(WhatsAppGrupo(codigo=codigo, nome=nome, tipo=tipo, ordem=ordem, ativo=True))
        added += 1
    if added:
        db.commit()
        logger.info("[Portal] %s grupo(s) WhatsApp padrão criados.", added)


def base_url_from_request(request: Request) -> str:
    return (os.getenv("APP_BASE_URL") or str(request.base_url)).rstrip("/")


def pwa_url_from_request(request: Request) -> str:
    return f"{base_url_from_request(request)}/m/"


def _pwa_enabled(db: Session) -> bool:
    cfg = db.query(Configuracao).filter(Configuracao.id == 1).first()
    return bool(cfg and cfg.pwa_enabled)


def _digits_phone(raw: str | None) -> str:
    if not raw:
        return ""
    return re.sub(r"\D+", "", raw.strip())


def normalize_wa_phone(raw: str | None) -> str:
    """Retorna dígitos com DDI 55 quando for celular BR (10/11 dígitos)."""
    phone = _digits_phone(raw)
    if not phone:
        return ""
    if len(phone) in (10, 11) and not phone.startswith("55"):
        phone = "55" + phone
    return phone


def wa_send_url(message: str, telefone: str | None = None) -> str:
    """URL que abre o WhatsApp com texto pré-preenchido."""
    text = quote(message)
    phone = normalize_wa_phone(telefone)
    if phone:
        return f"https://wa.me/{phone}?text={text}"
    return f"https://wa.me/?text={text}"


def build_evento_wa_message(
    *,
    evento_titulo: str,
    data_fmt: str,
    local: str | None,
    pwa_url: str,
    grupo_nome: str,
    institucion: str = "",
) -> str:
    org = (institucion or "").strip() or "Portal do Membro"
    local_line = f"Local: {local}\n" if local else ""
    return (
        f"🎻 {org} — Partituras\n\n"
        f"Evento: *{evento_titulo}*\n"
        f"Data: {data_fmt}\n"
        f"{local_line}"
        f"Grupo: *{grupo_nome}*\n\n"
        f"Acesse no celular (site mobile / PWA):\n"
        f"{pwa_url}\n\n"
        f"1) Abra o link\n"
        f"2) Entre com seu usuário do portal\n"
        f"3) Baixe as partituras do evento\n"
    )


def list_grupos_com_telefone(db: Session) -> list[WhatsAppGrupo]:
    """Grupos ativos que têm telefone cadastrado para envio."""
    ensure_whatsapp_grupos(db)
    grupos = (
        db.query(WhatsAppGrupo)
        .filter(WhatsAppGrupo.ativo == True)  # noqa: E712
        .order_by(WhatsAppGrupo.ordem, WhatsAppGrupo.nome)
        .all()
    )
    return [g for g in grupos if normalize_wa_phone(g.telefone)]


def build_evento_wa_payloads(
    db: Session,
    request: Request,
    *,
    evento_titulo: str,
    data_fmt: str,
    local: str | None,
) -> list[dict]:
    """Lista {nome, telefone, wa_send_url, mensagem} para cada grupo com telefone."""
    cfg = db.query(Configuracao).filter(Configuracao.id == 1).first()
    institucion = (cfg.nome_institucional if cfg else "") or ""
    pwa_url = pwa_url_from_request(request)
    out: list[dict] = []
    for g in list_grupos_com_telefone(db):
        msg = build_evento_wa_message(
            evento_titulo=evento_titulo,
            data_fmt=data_fmt,
            local=local,
            pwa_url=pwa_url,
            grupo_nome=g.nome,
            institucion=institucion,
        )
        out.append({
            "id": g.id,
            "nome": g.nome,
            "tipo": g.tipo,
            "telefone": g.telefone or "",
            "phone_e164": normalize_wa_phone(g.telefone),
            "mensagem": msg,
            "wa_send_url": wa_send_url(msg, g.telefone),
        })
    return out


def _build_message(grupo: WhatsAppGrupo, pwa_url: str, institucion: str = "") -> str:
    org = institucion.strip() or "Portal do Membro"
    return (
        f"🎻 {org} — Site mobile / PWA\n\n"
        f"Grupo: *{grupo.nome}*\n\n"
        f"Acesse suas partituras no celular:\n"
        f"{pwa_url}\n\n"
        f"1) Abra o link\n"
        f"2) Entre com seu usuário do portal\n"
        f"3) Opcional: Adicionar à tela inicial\n"
    )


def _normalize_group_url(raw: str) -> str | None:
    url = (raw or "").strip()
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url[:500]
    if url.startswith("chat.whatsapp.com/"):
        return f"https://{url}"[:500]
    return url[:500]


def _serialize_grupo(g: WhatsAppGrupo, pwa_url: str, institucion: str) -> dict:
    msg = _build_message(g, pwa_url, institucion)
    return {
        "id": g.id,
        "codigo": g.codigo,
        "nome": g.nome,
        "tipo": g.tipo,
        "whatsapp_url": g.whatsapp_url or "",
        "telefone": g.telefone or "",
        "ordem": g.ordem,
        "ativo": g.ativo,
        "mensagem": msg,
        "wa_send_url": wa_send_url(msg, g.telefone),
        "tem_grupo": bool(g.whatsapp_url),
        "tem_telefone": bool(normalize_wa_phone(g.telefone)),
    }


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def whatsapp_pwa_page(
    request: Request,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    ensure_whatsapp_grupos(db)
    pwa_url = pwa_url_from_request(request)
    pwa_on = _pwa_enabled(db)
    cfg = db.query(Configuracao).filter(Configuracao.id == 1).first()
    institucion = (cfg.nome_institucional if cfg else "") or ""

    grupos = (
        db.query(WhatsAppGrupo)
        .filter(WhatsAppGrupo.ativo == True)  # noqa: E712
        .order_by(WhatsAppGrupo.ordem, WhatsAppGrupo.nome)
        .all()
    )
    items = [_serialize_grupo(g, pwa_url, institucion) for g in grupos]
    orch = [i for i in items if i["tipo"] == "orquestra"]
    coral = [i for i in items if i["tipo"] == "coral"]
    outros = [i for i in items if i["tipo"] not in {"orquestra", "coral"}]

    ok = (request.query_params.get("ok") or "").strip()
    flash = None
    if ok == "saved":
        flash = {"message": "Grupos WhatsApp salvos.", "variant": "success"}

    ctx = make_ctx(request, {
        "pwa_url": pwa_url,
        "pwa_enabled": pwa_on,
        "grupos_orquestra": orch,
        "grupos_coral": coral,
        "grupos_outros": outros,
        "settings_section": "sistema",
        "settings_flash": flash,
        "settings_flash_json": json.dumps(flash, ensure_ascii=False) if flash else "null",
    })
    resp = templates.TemplateResponse("settings/whatsapp_pwa.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.post("/save")
async def whatsapp_pwa_save(
    request: Request,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    from app.audit import audit_from_request

    form = await request.form()
    updated = 0
    grupos = db.query(WhatsAppGrupo).all()
    for g in grupos:
        url_key = f"whatsapp_url_{g.id}"
        tel_key = f"telefone_{g.id}"
        if url_key not in form and tel_key not in form:
            continue
        new_url = _normalize_group_url(str(form.get(url_key, "") or ""))
        new_tel = _digits_phone(str(form.get(tel_key, "") or "")) or None
        if new_tel and len(new_tel) < 10:
            new_tel = None
        if (g.whatsapp_url or None) != new_url or (g.telefone or None) != new_tel:
            g.whatsapp_url = new_url
            g.telefone = new_tel
            updated += 1

    db.commit()
    audit_from_request(
        request,
        action="settings.whatsapp_pwa",
        entity_type="whatsapp_grupos",
        entity_id="*",
        summary=f"Atualizou links WhatsApp de {updated} grupo(s)",
        meta={"updated": updated},
    )
    logger.info("[Portal] WhatsApp PWA grupos atualizados: %s", updated)
    resp = RedirectResponse(url="/settings/whatsapp-pwa?ok=saved", status_code=303)
    return set_lang_cookie(resp, get_lang(request))
