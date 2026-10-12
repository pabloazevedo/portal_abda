"""
Portal — Release notes / histórico de versões.

A versão “atual” do portal vem do arquivo VERSION (ou APP_VERSION de emergência).
O banco guarda o histórico (release notes) e espelha a versão do código em is_current.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import make_ctx, require_admin, set_lang_cookie
from app.models import ReleaseNote
from app.version import get_version

router = APIRouter()
templates = Jinja2Templates(directory="templates")

_VERSION_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){1,3}([a-zA-Z0-9\-.]{0,16})?$")

_DEFAULT_NOTES_1_0_0 = (
    "### Adicionado\n"
    "- Portal do Membro disponível para a associação\n"
    "- Gestão de membros, papéis e instrumentos\n"
    "- Inventário de patrimônio com etiquetas\n"
    "- Acervo musical (obras, arranjos e programação)\n"
    "- Configurações institucionais e branding"
)

_NOTES_1_1_0 = (
    "### Adicionado\n"
    "- Arquivo VERSION como fonte de verdade da versão da aplicação\n"
    "- Página pública de histórico de versões (/versoes)\n"
    "- Release notes no banco e gestão em Configurações → Versões\n"
    "- Sincronização automática código ↔ versão atual no banco\n"
    "\n"
    "### Alterado\n"
    "- Rodapé exibe a versão do repositório e linka para o histórico"
)

_NOTES_1_2_0 = (
    "### Adicionado\n"
    "- Acesso ao App (PWA) no cadastro de Membros\n"
    "- Remoção de acesso ao App na ficha do membro (Admin)\n"
    "\n"
    "### Alterado\n"
    "- Usuários = equipe de sistema; Membros = músicos/coralistas + acesso ao app\n"
    "\n"
    "### Corrigido\n"
    "- Separação entre contas artísticas e operacionais do portal"
)

_NOTES_1_3_0 = (
    "### Adicionado\n"
    "- QR e código de barras gerados automaticamente no cadastro do item\n"
    "- Impressão formatada para impressoras de etiquetas (QR, barras ou ambos)\n"
    "\n"
    "### Alterado\n"
    "- QR/código de barras não são mais cadastrados manualmente\n"
    "\n"
    "### Corrigido\n"
    "- Scan resolve identificador e barcode do sistema"
)

_NOTES_1_3_1 = (
    "### Adicionado\n"
    "- Pré-visualização PDF da Grade no Detalhe da Obra\n"
    "- Visualização inline de documentos do acervo"
)


def normalize_version(raw: str) -> str:
    return (raw or "").strip().lstrip("vV")


def validate_version(version: str) -> str | None:
    if not version:
        return "Informe o número da versão."
    if len(version) > 32:
        return "Versão muito longa (máx. 32 caracteres)."
    if not _VERSION_RE.match(version):
        return "Formato inválido. Use algo como 1.0.0 ou 1.2.3-beta."
    return None


def code_version() -> str:
    """Versão publicada no rodapé / tags Git — sempre do código."""
    return get_version()


def list_release_notes(db: Session) -> list[ReleaseNote]:
    return (
        db.query(ReleaseNote)
        .order_by(ReleaseNote.released_at.desc(), ReleaseNote.id.desc())
        .all()
    )


def set_current_release(db: Session, note: ReleaseNote) -> None:
    """Marca uma release como atual.

    Usa UPDATE em SQL (não só o atributo ORM): um bulk update com
    synchronize_session=False pode deixar o identity map com is_current=True
    enquanto o banco já ficou False — aí note.is_current = True vira no-op
    e o commit não regrava a versão atual.
    """
    now = datetime.now(timezone.utc)
    db.query(ReleaseNote).update(
        {ReleaseNote.is_current: False},
        synchronize_session=False,
    )
    db.query(ReleaseNote).filter(ReleaseNote.id == note.id).update(
        {ReleaseNote.is_current: True, ReleaseNote.updated_at: now},
        synchronize_session=False,
    )
    note.is_current = True
    note.updated_at = now


def sync_code_version(db: Session, version: str | None = None) -> ReleaseNote:
    """Garante registro da versão do código e marca-a como atual no banco."""
    version = normalize_version(version or code_version()) or "0.0.0"
    note = db.query(ReleaseNote).filter(ReleaseNote.version == version).first()
    if note is None:
        defaults = {
            "1.0.0": ("Lançamento inicial", _DEFAULT_NOTES_1_0_0),
            "1.1.0": ("Versionamento no repositório e release notes", _NOTES_1_1_0),
            "1.2.0": ("Separação Membros × Usuários e acesso ao App", _NOTES_1_2_0),
            "1.3.0": ("QR e código de barras automáticos no inventário", _NOTES_1_3_0),
            "1.3.1": ("Pré-visualização da Grade no Detalhe da Obra", _NOTES_1_3_1),
        }
        title, notes = defaults.get(version, (f"Versão {version}", ""))
        note = ReleaseNote(
            version=version,
            title=title,
            notes=notes,
            released_at=date.today(),
            is_current=False,
        )
        db.add(note)
        db.flush()

    # Histórico 1.0.0 se esta for a primeira sync de 1.1.0+
    if version != "1.0.0" and db.query(ReleaseNote).filter(ReleaseNote.version == "1.0.0").first() is None:
        db.add(ReleaseNote(
            version="1.0.0",
            title="Lançamento inicial",
            notes=_DEFAULT_NOTES_1_0_0,
            released_at=date.today(),
            is_current=False,
        ))
        db.flush()

    set_current_release(db, note)
    db.commit()
    db.refresh(note)
    return note


def sync_app_version(request: Request, db: Session) -> str:
    version = code_version()
    sync_code_version(db, version)
    request.app.state.app_version = version
    return version


def ensure_release_notes_seed(db: Session, fallback_version: str | None = None) -> None:
    """Compat: sincroniza com a versão do código."""
    sync_code_version(db, fallback_version or code_version())


def get_current_version(db: Session | None = None, fallback: str | None = None) -> str:
    """Sempre a versão do código (DB é espelho)."""
    return code_version() or (fallback or "0.0.0")


# ──────────────────────────────────────────────────────────────
# Página pública (membros autenticados) — histórico
# ──────────────────────────────────────────────────────────────

@router.get("/versoes", response_class=HTMLResponse)
async def versoes_page(request: Request, db: Session = Depends(get_db)):
    notes = list_release_notes(db)
    current_ver = code_version()
    current = next((n for n in notes if n.version == current_ver), None)
    if current is None:
        current = next((n for n in notes if n.is_current), notes[0] if notes else None)
    ctx = make_ctx(request, {
        "release_notes": notes,
        "current_release": current,
        "code_version": current_ver,
    })
    return templates.TemplateResponse("release_notes/index.html", ctx)


# ──────────────────────────────────────────────────────────────
# Admin — CRUD das notas (versão atual = arquivo VERSION)
# ──────────────────────────────────────────────────────────────

admin_router = APIRouter(prefix="/settings/versoes")


def _admin_list_ctx(request: Request, db: Session, extra: dict | None = None) -> dict:
    data = {
        "release_notes": list_release_notes(db),
        "edit_note": None,
        "form_error": None,
        "code_version": code_version(),
    }
    if extra:
        data.update(extra)
    return make_ctx(request, data)


@admin_router.get("", response_class=HTMLResponse)
@admin_router.get("/", response_class=HTMLResponse)
async def admin_versoes_list(
    request: Request,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    ctx = _admin_list_ctx(request, db)
    resp = templates.TemplateResponse("settings/versoes.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@admin_router.get("/{note_id}/editar", response_class=HTMLResponse)
async def admin_versoes_edit(
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    note = db.query(ReleaseNote).filter(ReleaseNote.id == note_id).first()
    if note is None:
        return RedirectResponse("/settings/versoes", status_code=303)
    ctx = _admin_list_ctx(request, db, {"edit_note": note})
    resp = templates.TemplateResponse("settings/versoes.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@admin_router.post("/salvar")
async def admin_versoes_save(
    request: Request,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
    note_id: str | None = Form(None),
    version: str = Form(""),
    title: str = Form(""),
    notes: str = Form(""),
    released_at: str = Form(""),
):
    parsed_id: int | None = None
    if note_id and str(note_id).strip().isdigit():
        parsed_id = int(str(note_id).strip())

    version = normalize_version(version)
    title = (title or "").strip()[:200]
    notes = (notes or "").strip()
    err = validate_version(version)
    current = code_version()

    try:
        release_date = date.fromisoformat(released_at.strip()) if released_at.strip() else None
    except ValueError:
        release_date = None
        err = err or "Data de lançamento inválida."

    if release_date is None and not err:
        err = "Informe a data de lançamento."

    note: ReleaseNote | None = None
    if parsed_id:
        note = db.query(ReleaseNote).filter(ReleaseNote.id == parsed_id).first()
        if note is None:
            err = err or "Versão não encontrada."
        elif note.version == current and version != current:
            err = err or f"Não altere o número da versão atual ({current}). Edite o arquivo VERSION no código."

    if not err:
        clash = (
            db.query(ReleaseNote)
            .filter(ReleaseNote.version == version)
            .filter(ReleaseNote.id != (note.id if note else -1))
            .first()
        )
        if clash:
            err = f"A versão {version} já existe."

    if err:
        ctx = _admin_list_ctx(request, db, {
            "form_error": err,
            "edit_note": note or ReleaseNote(
                id=parsed_id or 0,
                version=version,
                title=title,
                notes=notes,
                released_at=release_date or date.today(),
                is_current=(version == current),
            ),
        })
        resp = templates.TemplateResponse("settings/versoes.html", ctx, status_code=400)
        return set_lang_cookie(resp, ctx["lang"])

    if note is None:
        note = ReleaseNote(
            version=version,
            title=title or f"Versão {version}",
            notes=notes,
            released_at=release_date,
            is_current=False,
            created_by=_admin.get("id"),
        )
        db.add(note)
        db.flush()
    else:
        note.version = version
        note.title = title or f"Versão {version}"
        note.notes = notes
        note.released_at = release_date
        note.updated_at = datetime.now(timezone.utc)

    db.commit()
    sync_app_version(request, db)
    return RedirectResponse("/settings/versoes", status_code=303)


@admin_router.post("/{note_id}/excluir")
async def admin_versoes_delete(
    note_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _admin: dict = Depends(require_admin),
):
    note = db.query(ReleaseNote).filter(ReleaseNote.id == note_id).first()
    if note is None:
        return RedirectResponse("/settings/versoes", status_code=303)

    if note.version == code_version():
        ctx = _admin_list_ctx(request, db, {
            "form_error": f"Não é possível excluir a versão atual do código ({code_version()}). Altere o arquivo VERSION primeiro.",
        })
        resp = templates.TemplateResponse("settings/versoes.html", ctx, status_code=400)
        return set_lang_cookie(resp, ctx["lang"])

    db.delete(note)
    db.commit()
    sync_app_version(request, db)
    return RedirectResponse("/settings/versoes", status_code=303)
