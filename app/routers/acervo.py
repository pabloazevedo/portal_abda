"""
Portal — Router do Acervo Musical.
Gerencia Obras e Arranjos (cadastros independentes).
Busca avançada e histórico de execuções.
"""

import json
import logging
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import (
    make_ctx, set_lang_cookie,
    require_manage_acervo, can_manage_acervo,
)
from app.models import (
    Obra, Arranjo, ConcertoArranjo, ArranjoDocumento,
    GeneroMusical, CopyrightStatus, Musician, MemberRole, RoleType, User,
    InstrumentoBase,
)
from app.search_index import DocumentoSearchIndex
from app.constants import INSTRUMENTOS_PADRAO
from app.acervo_storage import salvar_upload, validar_arquivo_partitura, url_download

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/acervo")
templates = Jinja2Templates(directory="templates")

PARTITURA_DIR = Path("uploads/partituras")
ALLOWED_EXT   = {".pdf", ".xml", ".mxl", ".mus", ".sib", ".musicxml"}

GENERO_LABELS = {
    GeneroMusical.sinfonia:      "Sinfonia",
    GeneroMusical.concerto:      "Concerto",
    GeneroMusical.camara:        "Câmara",
    GeneroMusical.coral:         "Coral",
    GeneroMusical.opera:         "Ópera",
    GeneroMusical.sacra:         "Sacra",
    GeneroMusical.popular:       "Popular",
    GeneroMusical.folclorica:    "Folclórica",
    GeneroMusical.contemporanea: "Contemporânea",
    GeneroMusical.outro:         "Outro",
}

COPYRIGHT_LABELS = {
    CopyrightStatus.dominio_publico: "Domínio Público",
    CopyrightStatus.licenciado:      "Licenciado",
    CopyrightStatus.pendente:        "Pendente",
}


# ── Helpers ────────────────────────────────────────────────────

def _parse_int(val) -> Optional[int]:
    try:
        return int(str(val).strip()) if val and str(val).strip() else None
    except ValueError:
        return None


def _save_partitura(upload: UploadFile) -> str:
    """Salva partitura em diretório legado (retrocompatibilidade)."""
    PARTITURA_DIR.mkdir(parents=True, exist_ok=True)
    ext = Path(upload.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(422, f"Formato não suportado. Use: {', '.join(ALLOWED_EXT)}")
    filename = f"{uuid.uuid4()}{ext}"
    dest = PARTITURA_DIR / filename
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f)
    return f"partituras/{filename}"


def _validar_upload_basico(upload: UploadFile) -> tuple[str, int]:
    """
    Validação básica: extensão + tamanho.
    Retorna (extension, file_size_bytes).
    """
    if not upload.filename:
        raise HTTPException(400, "Nome de arquivo vazio")

    ext = Path(upload.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(422, f"Formato não suportado. Use: {', '.join(ALLOWED_EXT)}")

    # Ler arquivo para verificar tamanho
    file_bytes = upload.file.read()
    upload.file.seek(0)

    MAX_SIZE_MB = 50
    if len(file_bytes) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(422, f"Arquivo muito grande (máx {MAX_SIZE_MB}MB)")

    return ext, len(file_bytes)


def _salvar_documento_disco(
    upload: UploadFile,
    arranjo_id: int,
    tipo: str,  # "grade", "instrumento", "coral", "acompanhamento"
    instrumento_nome: Optional[str] = None,
) -> str:
    """
    Salva documento em estrutura de diretórios.

    Estrutura:
    uploads/obras/
      ├── {arranjo_id}/
      │   ├── grade/
      │   ├── instrumentos/
      │   └── coral/

    Retorna: caminho relativo (ex: "obras/123/grade/score.pdf")
    """
    OBRAS_DIR = Path("uploads/obras")
    OBRAS_DIR.mkdir(parents=True, exist_ok=True)

    # Criar diretório base do arranjo
    arranjo_dir = OBRAS_DIR / str(arranjo_id)
    arranjo_dir.mkdir(exist_ok=True)

    # Criar subdiretório por tipo
    if tipo == "grade":
        subdir = arranjo_dir / "grade"
    elif tipo == "instrumento":
        subdir = arranjo_dir / "instrumentos"
    elif tipo == "coral":
        subdir = arranjo_dir / "coral"
    else:
        subdir = arranjo_dir / "outros"

    subdir.mkdir(exist_ok=True)

    # Salvar com nome original (ou UUID se duplicado)
    ext = Path(upload.filename).suffix.lower()
    filename = Path(upload.filename).stem + ext
    dest = subdir / filename

    # Se arquivo já existe, adicionar UUID
    if dest.exists():
        filename = f"{Path(upload.filename).stem}_{uuid.uuid4().hex[:8]}{ext}"
        dest = subdir / filename

    # Escrever arquivo
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f)

    # Retornar caminho relativo
    return str(dest.relative_to(Path("uploads")))


def _salvar_documento_temporario(
    upload: UploadFile,
    arranjo_id: int,
) -> tuple[str, str]:
    """
    Salva documento em pasta temporária para batch processing.

    Estrutura:
    uploads/temp/{arranjo_id}/{uuid_aleatorio}

    Retorna: (caminho_relativo, uuid_arquivo)
    """
    TEMP_DIR = Path("uploads/temp")
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    arranjo_temp_dir = TEMP_DIR / str(arranjo_id)
    arranjo_temp_dir.mkdir(exist_ok=True)

    # Gerar UUID único para esse upload
    file_id = uuid.uuid4().hex[:16]
    ext = Path(upload.filename).suffix.lower()
    filename = f"{file_id}{ext}"
    dest = arranjo_temp_dir / filename

    # Salvar arquivo
    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f)

    caminho_relativo = str(dest.relative_to(Path("uploads")))
    return caminho_relativo, file_id


def _mover_temporario_para_permanente(
    temp_caminho: str,
    arranjo_id: int,
    tipo: str,
    nome_original: str,
) -> tuple[str, int]:
    """
    Move arquivo de uploads/temp para uploads/obras/{arranjo_id}/{tipo}/.

    Retorna: (caminho permanente relativo, tamanho_bytes)
    """
    TEMP_PATH = Path("uploads") / temp_caminho

    if not TEMP_PATH.is_file():
        raise FileNotFoundError(f"Arquivo temporário não encontrado: {temp_caminho}")

    tamanho = TEMP_PATH.stat().st_size

    OBRAS_DIR = Path("uploads/obras")
    OBRAS_DIR.mkdir(parents=True, exist_ok=True)

    arranjo_dir = OBRAS_DIR / str(arranjo_id)
    arranjo_dir.mkdir(exist_ok=True)

    if tipo == "grade":
        subdir = arranjo_dir / "grade"
    elif tipo == "instrumento":
        subdir = arranjo_dir / "instrumentos"
    elif tipo == "coral":
        subdir = arranjo_dir / "coral"
    else:
        subdir = arranjo_dir / "outros"

    subdir.mkdir(exist_ok=True)

    ext = Path(nome_original).suffix.lower() or TEMP_PATH.suffix
    stem = Path(nome_original).stem or TEMP_PATH.stem
    filename = f"{stem}{ext}"
    dest = subdir / filename

    if dest.exists():
        filename = f"{stem}_{uuid.uuid4().hex[:8]}{ext}"
        dest = subdir / filename

    shutil.move(str(TEMP_PATH.resolve()), str(dest.resolve()))
    return str(dest.relative_to(Path("uploads"))), tamanho


def _membros_comp_arr(db: Session) -> list:
    return (
        db.query(Musician)
        .filter(
            Musician.is_active == True,
            Musician.roles.any(MemberRole.role_type.in_([
                RoleType.compositor, RoleType.arranjador, RoleType.musico
            ]))
        )
        .order_by(Musician.first_name, Musician.last_name)
        .all()
    )


def _indexar_documento(db: Session, documento: ArranjoDocumento, arranjo: Arranjo) -> None:
    """Indexa documento no SearchIndex FTS."""
    obra = arranjo.obra
    search_index = DocumentoSearchIndex()
    search_index.indexar(
        documento_id=documento.id,
        arranjo_id=arranjo.id,
        titulo_obra=obra.titulo if obra else (arranjo.titulo_arranjo or ""),
        compositor=obra.compositor_label if obra else "",
        tipo_documento=documento.tipo,
        instrumento=documento.instrumento_nome or documento.stab_tipo or "",
        caminho_arquivo=documento.arquivo_caminho,
    )
    search_index.close()


def _ctx_obra_form(request, db, obra=None, error=None, extra=None):
    ctx = make_ctx(request, {
        "obra": obra,
        "generos": list(GeneroMusical),
        "genero_labels": GENERO_LABELS,
        "membros": _membros_comp_arr(db),
        "copyright_list": list(CopyrightStatus),
        "copyright_labels": COPYRIGHT_LABELS,
        "instrumentos_padrao": INSTRUMENTOS_PADRAO,
        "error": error,
        "form_data": {},
    })
    if extra:
        ctx.update(extra)
    return ctx


@router.get("/obras/new", response_class=HTMLResponse)
def obra_new_form(
    request: Request,
    db: Session = Depends(get_db),
    _user=Depends(require_manage_acervo),
):
    ctx = _ctx_obra_form(request, db)
    resp = templates.TemplateResponse("acervo/obra_form.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.post("/obras/new")
async def obra_new_save(
    request: Request,
    titulo: str              = Form(...),
    titulo_original: str     = Form(""),
    compositor_id: str       = Form(""),
    compositor_nome: str     = Form(""),
    genero: str              = Form("outro"),
    tonalidade: str          = Form(""),
    ano_composicao: str      = Form(""),
    observacoes: str         = Form(""),
    instrumentacao: str      = Form(""),
    arranjador_id: str       = Form(""),
    arranjador_nome: str     = Form(""),
    duracao_min: str         = Form(""),
    duracao_seg: str         = Form(""),
    editora: str             = Form(""),
    copyright_status: str    = Form("pendente"),
    numero_licenca: str      = Form(""),
    grade: UploadFile        = File(...),
    parte_instrumento_nome: list[str] = Form(default=[]),
    parte_arquivo: list[UploadFile] = File(default=[]),
    db: Session              = Depends(get_db),
    current_user             = Depends(require_manage_acervo),
):
    """Cadastro completo: obra + arranjo + grade + partes por instrumento."""
    # Normaliza gênero inválido para o form (ex.: valor legado/typo)
    if genero not in GeneroMusical._value2member_map_:
        genero = "outro"

    form_data = {
        "titulo": titulo,
        "titulo_original": titulo_original,
        "compositor_id": compositor_id,
        "compositor_nome": compositor_nome,
        "genero": genero,
        "tonalidade": tonalidade,
        "ano_composicao": ano_composicao,
        "observacoes": observacoes,
        "instrumentacao": instrumentacao,
        "arranjador_id": arranjador_id,
        "arranjador_nome": arranjador_nome,
        "duracao_min": duracao_min,
        "duracao_seg": duracao_seg,
        "editora": editora,
        "copyright_status": copyright_status if copyright_status in CopyrightStatus._value2member_map_ else "pendente",
        "numero_licenca": numero_licenca,
    }

    def _error(msg: str):
        ctx = _ctx_obra_form(request, db, error=msg, extra={"form_data": form_data})
        resp = templates.TemplateResponse("acervo/obra_form.html", ctx, status_code=422)
        return set_lang_cookie(resp, ctx["lang"])

    if not titulo.strip():
        return _error("Informe o título da obra.")

    if not compositor_id and not compositor_nome.strip():
        return _error("Informe o compositor (membro ou nome externo).")

    if not instrumentacao.strip():
        return _error("Informe a instrumentação do arranjo.")

    if copyright_status == "licenciado" and not numero_licenca.strip():
        return _error("Número de licença obrigatório para obras licenciadas.")

    if not grade.filename:
        return _error("A partitura da grade (maestro) é obrigatória.")

    try:
        validar_arquivo_partitura(grade)
    except HTTPException as e:
        return _error(str(e.detail))

    obra = Obra(
        titulo          = titulo.strip(),
        titulo_original = titulo_original.strip() or None,
        compositor_id   = _parse_int(compositor_id),
        compositor_nome = compositor_nome.strip() or None,
        genero          = GeneroMusical(genero) if genero in GeneroMusical._value2member_map_ else GeneroMusical.outro,
        tonalidade      = tonalidade.strip() or None,
        ano_composicao  = _parse_int(ano_composicao),
        observacoes     = observacoes.strip() or None,
        created_by      = current_user["id"],
    )
    db.add(obra)
    db.flush()

    m = _parse_int(duracao_min) or 0
    s = _parse_int(duracao_seg) or 0

    arranjo = Arranjo(
        obra_id          = obra.id,
        titulo_arranjo   = "Arranjo principal",
        arranjador_id    = _parse_int(arranjador_id),
        arranjador_nome  = arranjador_nome.strip() or None,
        instrumentacao   = instrumentacao.strip(),
        duracao_segundos = (m * 60 + s) if (m or s) else None,
        editora          = editora.strip() or None,
        copyright_status = CopyrightStatus(copyright_status) if copyright_status in CopyrightStatus._value2member_map_ else CopyrightStatus.pendente,
        numero_licenca   = numero_licenca.strip() or None,
        created_by       = current_user["id"],
    )
    db.add(arranjo)
    db.flush()

    # Grade do maestro
    caminho_grade, tamanho_grade, _ = salvar_upload(grade, arranjo.id, "grade")
    doc_grade = ArranjoDocumento(
        arranjo_id=arranjo.id,
        tipo="grade",
        arquivo_caminho=caminho_grade,
        tamanho_bytes=tamanho_grade,
        created_by=current_user["id"],
    )
    db.add(doc_grade)
    db.flush()
    _indexar_documento(db, doc_grade, arranjo)
    arranjo.arquivo_partitura = caminho_grade

    # Partes por instrumento
    partes_validas = [
        (nome.strip(), arq)
        for nome, arq in zip(parte_instrumento_nome, parte_arquivo)
        if nome.strip() and arq and arq.filename
    ]

    for inst_nome, arquivo in partes_validas:
        try:
            caminho, tamanho, _ = salvar_upload(arquivo, arranjo.id, "instrumento", inst_nome)
        except HTTPException as e:
            db.rollback()
            return _error(f"Parte '{inst_nome}': {e.detail}")

        doc_parte = ArranjoDocumento(
            arranjo_id=arranjo.id,
            tipo="instrumento",
            instrumento_nome=inst_nome,
            arquivo_caminho=caminho,
            tamanho_bytes=tamanho,
            created_by=current_user["id"],
        )
        db.add(doc_parte)
        db.flush()
        _indexar_documento(db, doc_parte, arranjo)

    db.commit()
    return RedirectResponse(url=f"/acervo/obras/{obra.id}", status_code=303)


def _documento_path(doc: ArranjoDocumento) -> Path:
    return Path("uploads") / doc.arquivo_caminho


@router.get("/documentos/{documento_id}/download")
def download_documento(
    documento_id: int,
    db: Session = Depends(get_db),
):
    """Download autenticado de documento do acervo."""
    doc = db.query(ArranjoDocumento).filter_by(id=documento_id).first()
    if not doc:
        raise HTTPException(404, "Documento não encontrado")
    path = _documento_path(doc)
    if not path.exists():
        raise HTTPException(404, "Arquivo não encontrado no servidor")
    return FileResponse(path, filename=path.name)


@router.get("/documentos/{documento_id}/view")
def view_documento(
    documento_id: int,
    db: Session = Depends(get_db),
):
    """Visualização inline (PDF no browser) — usada no sample da grade."""
    doc = db.query(ArranjoDocumento).filter_by(id=documento_id).first()
    if not doc:
        raise HTTPException(404, "Documento não encontrado")
    path = _documento_path(doc)
    if not path.exists():
        raise HTTPException(404, "Arquivo não encontrado no servidor")
    media = "application/pdf" if path.suffix.lower() == ".pdf" else "application/octet-stream"
    return FileResponse(
        path,
        media_type=media,
        filename=path.name,
        content_disposition_type="inline",
    )


def _primeira_grade(obra: Obra) -> ArranjoDocumento | None:
    """Retorna o documento tipo grade do primeiro arranjo que tiver um."""
    for arranjo in obra.arranjos or []:
        for doc in arranjo.documentos or []:
            if doc.tipo == "grade":
                return doc
        # Legado: arquivo_partitura sem ArranjoDocumento
        if arranjo.arquivo_partitura and not (arranjo.documentos or []):
            return None
    return None


# ── Redirect raiz ──────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
def acervo_home(request: Request):
    return RedirectResponse(url="/acervo/obras", status_code=302)


# ══════════════════════════════════════════════════════════════
# OBRAS
# ══════════════════════════════════════════════════════════════

@router.get("/obras", response_class=HTMLResponse)
def obras_list(
    request: Request,
    q: str = "",
    compositor: str = "",
    genero: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Obra)
    if q:
        query = query.filter(Obra.titulo.ilike(f"%{q}%"))
    if compositor:
        from sqlalchemy import or_
        query = query.filter(
            or_(
                Obra.compositor_nome.ilike(f"%{compositor}%"),
            )
        )
    if genero:
        try:
            query = query.filter(Obra.genero == GeneroMusical(genero))
        except ValueError:
            pass
    obras = query.order_by(Obra.titulo).all()
    ctx = make_ctx(request, {
        "obras": obras,
        "generos": list(GeneroMusical),
        "genero_labels": GENERO_LABELS,
        "q": q,
        "filtro_compositor": compositor,
        "filtro_genero": genero,
    })
    resp = templates.TemplateResponse("acervo/obras_list.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.get("/obras/{obra_id}", response_class=HTMLResponse)
def obra_detail(request: Request, obra_id: int, db: Session = Depends(get_db)):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(404, "Obra não encontrada")
    grade_doc = _primeira_grade(obra)
    grade_is_pdf = False
    if grade_doc and grade_doc.arquivo_caminho:
        grade_is_pdf = Path(grade_doc.arquivo_caminho).suffix.lower() == ".pdf"
    ctx = make_ctx(request, {
        "obra": obra,
        "genero_labels": GENERO_LABELS,
        "copyright_labels": COPYRIGHT_LABELS,
        "erro": request.query_params.get("erro"),
        "grade_doc": grade_doc,
        "grade_is_pdf": grade_is_pdf,
    })
    resp = templates.TemplateResponse("acervo/obra_detail.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.get("/obras/{obra_id}/edit", response_class=HTMLResponse)
def obra_edit_form(
    request: Request,
    obra_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_manage_acervo),
):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(404)
    ctx = _ctx_obra_form(request, db, obra=obra)
    resp = templates.TemplateResponse("acervo/obra_form.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.post("/obras/{obra_id}/edit")
async def obra_edit_save(
    request: Request,
    obra_id: int,
    titulo: str           = Form(...),
    titulo_original: str  = Form(""),
    compositor_id: str    = Form(""),
    compositor_nome: str  = Form(""),
    genero: str           = Form("outro"),
    tonalidade: str       = Form(""),
    ano_composicao: str   = Form(""),
    observacoes: str      = Form(""),
    db: Session           = Depends(get_db),
    current_user          = Depends(require_manage_acervo),
):
    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(404)
    if not compositor_id and not compositor_nome.strip():
        ctx = _ctx_obra_form(request, db, obra=obra, error="Informe o compositor (membro ou nome externo).")
        return templates.TemplateResponse("acervo/obra_form.html", ctx, status_code=422)

    obra.titulo          = titulo.strip()
    obra.titulo_original = titulo_original.strip() or None
    obra.compositor_id   = _parse_int(compositor_id)
    obra.compositor_nome = compositor_nome.strip() or None
    obra.genero          = GeneroMusical(genero) if genero in GeneroMusical._value2member_map_ else GeneroMusical.outro
    obra.tonalidade      = tonalidade.strip() or None
    obra.ano_composicao  = _parse_int(ano_composicao)
    obra.observacoes     = observacoes.strip() or None
    db.commit()
    return RedirectResponse(url=f"/acervo/obras/{obra_id}", status_code=303)


@router.post("/obras/{obra_id}/delete")
def obra_delete(
    request: Request,
    obra_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_manage_acervo),
):
    from urllib.parse import quote

    obra = db.query(Obra).filter(Obra.id == obra_id).first()
    if not obra:
        raise HTTPException(404)

    # Qualquer vínculo em programa bloqueia (FK RESTRICT em concerto_arranjos)
    vinculos = db.execute(text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE ca.data_execucao IS NOT NULL) AS execucoes
        FROM concerto_arranjos ca
        JOIN arranjos a ON a.id = ca.arranjo_id
        WHERE a.obra_id = :oid
    """), {"oid": obra_id}).mappings().first()

    if vinculos and vinculos["total"]:
        if vinculos["execucoes"]:
            detalhe = "Não é possível excluir: esta obra possui histórico de execuções registradas."
        else:
            detalhe = (
                "Não é possível excluir: um ou mais arranjos desta obra estão no programa "
                "de um evento. Remova-os da programação antes."
            )
        return RedirectResponse(
            url=f"/acervo/obras/{obra_id}?erro={quote(detalhe)}",
            status_code=303,
        )

    try:
        db.delete(obra)
        db.commit()
    except Exception:
        db.rollback()
        detalhe = "Não é possível excluir: a obra ainda está vinculada a eventos ou outros registros."
        return RedirectResponse(
            url=f"/acervo/obras/{obra_id}?erro={quote(detalhe)}",
            status_code=303,
        )
    return RedirectResponse(url="/acervo/obras", status_code=303)


# ══════════════════════════════════════════════════════════════
# ARRANJOS — cadastro independente (obra_id opcional)
# ══════════════════════════════════════════════════════════════

@router.get("/arranjos", response_class=HTMLResponse)
def arranjos_list(
    request: Request,
    q: str = "",
    obra_id: str = "",
    copyright_filter: str = "",
    db: Session = Depends(get_db),
):
    query = db.query(Arranjo)
    if q:
        query = query.filter(Arranjo.instrumentacao.ilike(f"%{q}%"))
    if obra_id:
        oid = _parse_int(obra_id)
        if oid:
            query = query.filter(Arranjo.obra_id == oid)
    if copyright_filter:
        try:
            query = query.filter(Arranjo.copyright_status == CopyrightStatus(copyright_filter))
        except ValueError:
            pass
    arranjos = query.order_by(Arranjo.id.desc()).all()
    obras = db.query(Obra).order_by(Obra.titulo).all()
    ctx = make_ctx(request, {
        "arranjos": arranjos,
        "obras": obras,
        "copyright_labels": COPYRIGHT_LABELS,
        "copyright_list": list(CopyrightStatus),
        "q": q,
        "filtro_obra_id": obra_id,
        "filtro_copyright": copyright_filter,
        "erro": request.query_params.get("erro"),
    })
    resp = templates.TemplateResponse("acervo/arranjos_list.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.get("/arranjos/new", response_class=HTMLResponse)
def arranjo_standalone_form(
    request: Request,
    obra_id: str = "",
    db: Session = Depends(get_db),
    _user=Depends(require_manage_acervo),
):
    obra_presel = db.query(Obra).filter(Obra.id == _parse_int(obra_id)).first() if obra_id else None
    ctx = make_ctx(request, {
        "obra": None,
        "arranjo": None,
        "obras": db.query(Obra).order_by(Obra.titulo).all(),
        "obra_presel": obra_presel,
        "membros": _membros_comp_arr(db),
        "copyright_list": list(CopyrightStatus),
        "copyright_labels": COPYRIGHT_LABELS,
        "standalone": True,
        "error": None,
    })
    resp = templates.TemplateResponse("acervo/arranjo_form.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.post("/arranjos/new")
async def arranjo_standalone_save(
    request: Request,
    obra_id_sel: str       = Form(""),
    titulo_arranjo: str    = Form(""),
    arranjador_id: str     = Form(""),
    arranjador_nome: str   = Form(""),
    instrumentacao: str    = Form(...),
    duracao_min: str       = Form(""),
    duracao_seg: str       = Form(""),
    editora: str           = Form(""),
    copyright_status: str  = Form("pendente"),
    numero_licenca: str    = Form(""),
    partitura: UploadFile  = File(None),
    db: Session            = Depends(get_db),
    current_user           = Depends(require_manage_acervo),
):
    if copyright_status == "licenciado" and not numero_licenca.strip():
        ctx = make_ctx(request, {
            "obra": None, "arranjo": None, "standalone": True,
            "obras": db.query(Obra).order_by(Obra.titulo).all(),
            "obra_presel": None,
            "membros": _membros_comp_arr(db),
            "copyright_list": list(CopyrightStatus),
            "copyright_labels": COPYRIGHT_LABELS,
            "error": "Número de licença obrigatório para obras licenciadas.",
        })
        return templates.TemplateResponse("acervo/arranjo_form.html", ctx, status_code=422)

    m = _parse_int(duracao_min) or 0
    s = _parse_int(duracao_seg) or 0

    arranjo = Arranjo(
        obra_id          = _parse_int(obra_id_sel),
        titulo_arranjo   = titulo_arranjo.strip() or None,
        arranjador_id    = _parse_int(arranjador_id),
        arranjador_nome  = arranjador_nome.strip() or None,
        instrumentacao   = instrumentacao.strip(),
        duracao_segundos = (m * 60 + s) if (m or s) else None,
        editora          = editora.strip() or None,
        copyright_status = CopyrightStatus(copyright_status) if copyright_status in CopyrightStatus._value2member_map_ else CopyrightStatus.pendente,
        numero_licenca   = numero_licenca.strip() or None,
        arquivo_partitura= None,
        created_by       = current_user["id"],
    )
    db.add(arranjo)
    db.flush()

    if partitura and partitura.filename:
        try:
            caminho, tamanho, _ = salvar_upload(partitura, arranjo.id, "grade")
            doc_grade = ArranjoDocumento(
                arranjo_id=arranjo.id,
                tipo="grade",
                arquivo_caminho=caminho,
                tamanho_bytes=tamanho,
                created_by=current_user["id"],
            )
            db.add(doc_grade)
            db.flush()
            _indexar_documento(db, doc_grade, arranjo)
            arranjo.arquivo_partitura = caminho
        except HTTPException as e:
            db.rollback()
            ctx = make_ctx(request, {
                "obra": None, "arranjo": None, "standalone": True,
                "obras": db.query(Obra).order_by(Obra.titulo).all(),
                "obra_presel": db.query(Obra).filter(Obra.id == _parse_int(obra_id_sel)).first() if obra_id_sel else None,
                "membros": _membros_comp_arr(db),
                "copyright_list": list(CopyrightStatus),
                "copyright_labels": COPYRIGHT_LABELS,
                "error": e.detail,
            })
            return templates.TemplateResponse("acervo/arranjo_form.html", ctx, status_code=422)

    db.commit()
    db.refresh(arranjo)
    if arranjo.obra_id:
        return RedirectResponse(url=f"/acervo/obras/{arranjo.obra_id}", status_code=303)
    return RedirectResponse(url="/acervo/arranjos", status_code=303)


# Rota aninhada em obra (mantém UX de adicionar diretamente da obra)
@router.get("/obras/{obra_id}/arranjos/new", response_class=HTMLResponse)
def arranjo_from_obra_form(
    request: Request,
    obra_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_manage_acervo),
):
    return RedirectResponse(url=f"/acervo/arranjos/new?obra_id={obra_id}", status_code=302)


@router.get("/arranjos/{arranjo_id}/edit", response_class=HTMLResponse)
def arranjo_edit_form(
    request: Request,
    arranjo_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_manage_acervo),
):
    arranjo = db.query(Arranjo).filter(Arranjo.id == arranjo_id).first()
    if not arranjo:
        raise HTTPException(404)
    ctx = make_ctx(request, {
        "obra": arranjo.obra,
        "arranjo": arranjo,
        "obras": db.query(Obra).order_by(Obra.titulo).all(),
        "obra_presel": arranjo.obra,
        "membros": _membros_comp_arr(db),
        "copyright_list": list(CopyrightStatus),
        "copyright_labels": COPYRIGHT_LABELS,
        "standalone": arranjo.obra_id is None,
        "error": None,
    })
    resp = templates.TemplateResponse("acervo/arranjo_form.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.post("/arranjos/{arranjo_id}/edit")
async def arranjo_edit_save(
    request: Request,
    arranjo_id: int,
    obra_id_sel: str       = Form(""),
    titulo_arranjo: str    = Form(""),
    arranjador_id: str     = Form(""),
    arranjador_nome: str   = Form(""),
    instrumentacao: str    = Form(...),
    duracao_min: str       = Form(""),
    duracao_seg: str       = Form(""),
    editora: str           = Form(""),
    copyright_status: str  = Form("pendente"),
    numero_licenca: str    = Form(""),
    partitura: UploadFile  = File(None),
    db: Session            = Depends(get_db),
    current_user           = Depends(require_manage_acervo),
):
    arranjo = db.query(Arranjo).filter(Arranjo.id == arranjo_id).first()
    if not arranjo:
        raise HTTPException(404)

    if copyright_status == "licenciado" and not numero_licenca.strip():
        ctx = make_ctx(request, {
            "obra": arranjo.obra, "arranjo": arranjo, "standalone": arranjo.obra_id is None,
            "obras": db.query(Obra).order_by(Obra.titulo).all(),
            "obra_presel": arranjo.obra,
            "membros": _membros_comp_arr(db),
            "copyright_list": list(CopyrightStatus),
            "copyright_labels": COPYRIGHT_LABELS,
            "error": "Número de licença obrigatório para obras licenciadas.",
        })
        return templates.TemplateResponse("acervo/arranjo_form.html", ctx, status_code=422)

    m = _parse_int(duracao_min) or 0
    s = _parse_int(duracao_seg) or 0

    if partitura and partitura.filename:
        try:
            caminho, tamanho, _ = salvar_upload(partitura, arranjo.id, "grade")
            # Atualiza grade existente ou cria nova
            grade_existente = next((d for d in arranjo.documentos if d.tipo == "grade"), None)
            if grade_existente:
                grade_existente.arquivo_caminho = caminho
                grade_existente.tamanho_bytes = tamanho
                doc_grade = grade_existente
            else:
                doc_grade = ArranjoDocumento(
                    arranjo_id=arranjo.id,
                    tipo="grade",
                    arquivo_caminho=caminho,
                    tamanho_bytes=tamanho,
                    created_by=current_user["id"],
                )
                db.add(doc_grade)
                db.flush()
                _indexar_documento(db, doc_grade, arranjo)
            arranjo.arquivo_partitura = caminho
        except HTTPException as e:
            ctx = make_ctx(request, {
                "obra": arranjo.obra, "arranjo": arranjo, "standalone": arranjo.obra_id is None,
                "obras": db.query(Obra).order_by(Obra.titulo).all(),
                "obra_presel": arranjo.obra,
                "membros": _membros_comp_arr(db),
                "copyright_list": list(CopyrightStatus),
                "copyright_labels": COPYRIGHT_LABELS,
                "error": e.detail,
            })
            return templates.TemplateResponse("acervo/arranjo_form.html", ctx, status_code=422)

    arranjo.obra_id          = _parse_int(obra_id_sel)
    arranjo.titulo_arranjo   = titulo_arranjo.strip() or None
    arranjo.arranjador_id    = _parse_int(arranjador_id)
    arranjo.arranjador_nome  = arranjador_nome.strip() or None
    arranjo.instrumentacao   = instrumentacao.strip()
    arranjo.duracao_segundos = (m * 60 + s) if (m or s) else None
    arranjo.editora          = editora.strip() or None
    arranjo.copyright_status = CopyrightStatus(copyright_status) if copyright_status in CopyrightStatus._value2member_map_ else CopyrightStatus.pendente
    arranjo.numero_licenca   = numero_licenca.strip() or None
    db.commit()
    if arranjo.obra_id:
        return RedirectResponse(url=f"/acervo/obras/{arranjo.obra_id}", status_code=303)
    return RedirectResponse(url="/acervo/arranjos", status_code=303)


@router.get("/arranjos/{arranjo_id}/upload-coral", response_class=HTMLResponse)
def upload_coral_page(
    arranjo_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_manage_acervo),
):
    """Página de upload de partes coral (STAB ou partitura única)"""
    arranjo = db.query(Arranjo).get(arranjo_id)
    if not arranjo:
        raise HTTPException(404, "Arranjo não encontrado")

    ctx = make_ctx(request, {"arranjo": arranjo})
    resp = templates.TemplateResponse("acervo/arranjo_upload_coral.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.get("/arranjos/{arranjo_id}/upload-instrumento", response_class=HTMLResponse)
def upload_instrumento_page(
    arranjo_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_manage_acervo),
):
    """Página de upload de parte de orquestra com lista de instrumentos."""
    arranjo = db.query(Arranjo).get(arranjo_id)
    if not arranjo:
        raise HTTPException(404, "Arranjo não encontrado")

    nomes_db = [
        r.nome
        for r in (
            db.query(InstrumentoBase)
            .filter(InstrumentoBase.ativo == True)  # noqa: E712
            .order_by(InstrumentoBase.categoria, InstrumentoBase.nome)
            .all()
        )
    ]
    seen: set[str] = set()
    instrumentos: list[str] = []
    for nome in list(nomes_db) + list(INSTRUMENTOS_PADRAO):
        key = (nome or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        instrumentos.append(nome)

    ctx = make_ctx(request, {
        "arranjo": arranjo,
        "instrumentos_padrao": instrumentos,
    })
    resp = templates.TemplateResponse("acervo/arranjo_upload_instrumento.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


@router.post("/arranjos/{arranjo_id}/delete")
def arranjo_delete(
    request: Request,
    arranjo_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_manage_acervo),
):
    from urllib.parse import quote

    arranjo = db.query(Arranjo).filter(Arranjo.id == arranjo_id).first()
    if not arranjo:
        raise HTTPException(404)
    obra_id = arranjo.obra_id
    back = f"/acervo/obras/{obra_id}" if obra_id else "/acervo/arranjos"

    # FK concerto_arranjos.arranjo_id é RESTRICT — qualquer vínculo bloqueia
    vinculos = db.query(ConcertoArranjo).filter(
        ConcertoArranjo.arranjo_id == arranjo_id,
    ).all()
    if vinculos:
        tem_execucao = any(v.data_execucao is not None for v in vinculos)
        if tem_execucao:
            detalhe = "Não é possível excluir: arranjo possui histórico de execuções."
        else:
            detalhe = (
                "Não é possível excluir: arranjo está no programa de um evento. "
                "Remova-o da programação antes de excluir."
            )
        return RedirectResponse(url=f"{back}?erro={quote(detalhe)}", status_code=303)

    try:
        db.delete(arranjo)
        db.commit()
    except Exception:
        db.rollback()
        detalhe = (
            "Não é possível excluir: arranjo ainda está vinculado a um evento "
            "ou outros registros."
        )
        return RedirectResponse(url=f"{back}?erro={quote(detalhe)}", status_code=303)
    return RedirectResponse(url=back, status_code=303)


# ══════════════════════════════════════════════════════════════
# UPLOAD TEMPORÁRIO E BATCH PROCESSING
# ══════════════════════════════════════════════════════════════

@router.post("/arranjos/{arranjo_id}/upload-temp")
def upload_temp(
    arranjo_id: int,
    tipo: str = Form(...),  # "coral" ou "instrumento"
    stab_tipo: Optional[str] = Form(None),  # "soprano", "alto", "tenor", "baixo" (para coral)
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_manage_acervo),
):
    """
    Faz upload temporário de documento para processamento posterior.
    Retorna JSON com ID do arquivo temporário.
    """
    # Verificar se arranjo existe
    arranjo = db.query(Arranjo).get(arranjo_id)
    if not arranjo:
        raise HTTPException(404, "Arranjo não encontrado")

    # Validar upload
    _validar_upload_basico(arquivo)

    # Salvar temporário
    caminho_temp, file_id = _salvar_documento_temporario(arquivo, arranjo_id)

    return {
        "success": True,
        "file_id": file_id,
        "caminho_temp": caminho_temp,
        "tipo": tipo,
        "stab_tipo": stab_tipo,
        "nome_original": arquivo.filename,
    }


@router.post("/arranjos/{arranjo_id}/confirmar-uploads")
def confirmar_uploads(
    arranjo_id: int,
    uploads: str = Form(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_manage_acervo),
):
    """
    Move uploads temporários para permanente e cria registros em ArranjoDocumento.
    Indexa documentos no SearchIndex.
    """
    try:
        uploads_list = json.loads(uploads)
    except json.JSONDecodeError:
        raise HTTPException(422, "Formato de uploads inválido")

    arranjo = db.query(Arranjo).get(arranjo_id)
    if not arranjo:
        raise HTTPException(404, "Arranjo não encontrado")

    criados = []
    erros = []

    for upload_data in uploads_list:
        try:
            # Construir caminho temporário
            temp_caminho = f"temp/{arranjo_id}/{upload_data['file_id']}*"
            # Encontrar arquivo temporário (pode ter extensão)
            temp_dir = Path("uploads/temp") / str(arranjo_id)
            temp_files = list(temp_dir.glob(f"{upload_data['file_id']}*"))
            if not temp_files:
                erros.append(f"Arquivo temporário não encontrado: {upload_data['file_id']}")
                continue

            temp_file = temp_files[0]
            temp_caminho_relativo = str(temp_file.relative_to(Path("uploads")))

            # Mover para permanente (tamanho lido dentro do move, antes de apagar o temp)
            caminho_permanente, tamanho_bytes = _mover_temporario_para_permanente(
                temp_caminho_relativo,
                arranjo_id,
                upload_data["tipo"],
                upload_data["nome_original"],
            )

            # Criar registro em ArranjoDocumento
            documento = ArranjoDocumento(
                arranjo_id=arranjo_id,
                tipo=upload_data["tipo"],  # "coral", "instrumento", "grade", "acompanhamento"
                instrumento_nome=upload_data.get("instrumento_nome"),  # Para tipo="instrumento"
                stab_tipo=upload_data.get("stab_tipo"),  # "soprano", "alto", etc. para tipo="coral"
                arquivo_caminho=caminho_permanente,
                tamanho_bytes=tamanho_bytes,
                created_by=current_user["id"],
            )
            db.add(documento)
            db.flush()

            # Indexação é best-effort (não deve bloquear o upload)
            try:
                search_index = DocumentoSearchIndex()
                search_index.indexar(
                    documento_id=documento.id,
                    arranjo_id=arranjo_id,
                    titulo_obra=(arranjo.obra.titulo if arranjo.obra else None) or arranjo.titulo_arranjo or "",
                    compositor=arranjo.obra.compositor_nome if arranjo.obra else "",
                    tipo_documento=upload_data["tipo"],
                    instrumento=upload_data.get("instrumento_nome") or upload_data.get("stab_tipo") or "",
                    caminho_arquivo=caminho_permanente,
                )
                search_index.close()
            except Exception as idx_exc:
                logger.warning("Indexação FTS falhou (upload ok): %s", idx_exc)

            criados.append({
                "id": documento.id,
                "tipo": upload_data["tipo"],
                "stab_tipo": upload_data.get("stab_tipo"),
                "instrumento_nome": upload_data.get("instrumento_nome"),
                "arquivo_caminho": caminho_permanente,
            })

        except Exception as e:
            erros.append(f"Erro ao processar {upload_data.get('nome_original', 'desconhecido')}: {str(e)}")
            logger.error(f"Erro em confirmar-uploads: {e}")

    db.commit()

    return {
        "success": len(erros) == 0,
        "criados": criados,
        "erros": erros,
        "total": len(uploads_list),
        "processados": len(criados),
    }


# ══════════════════════════════════════════════════════════════
# BUSCA AVANÇADA
# ══════════════════════════════════════════════════════════════

@router.get("/busca", response_class=HTMLResponse)
def busca_page(
    request: Request,
    q: str = "",
    compositor: str = "",
    arranjador: str = "",
    instrumento: str = "",
    db: Session = Depends(get_db),
):
    resultados = []
    if q or compositor or arranjador or instrumento:
        resultados = db.execute(text("""
            SELECT
                o.id              AS obra_id,
                o.titulo,
                COALESCE(mc.first_name || ' ' || mc.last_name, o.compositor_nome) AS compositor,
                o.genero,
                o.tonalidade,
                a.id              AS arranjo_id,
                COALESCE(a.titulo_arranjo, 'Arranjo principal') AS titulo_arranjo,
                COALESCE(ma.first_name || ' ' || ma.last_name, a.arranjador_nome, '—') AS arranjador,
                a.instrumentacao,
                a.duracao_segundos,
                a.copyright_status
            FROM arranjos a
            LEFT JOIN obras o     ON o.id = a.obra_id
            LEFT JOIN musicians mc ON mc.id = o.compositor_id
            LEFT JOIN musicians ma ON ma.id = a.arranjador_id
            WHERE a.ativo = TRUE
              AND (:q IS NULL OR (
                    COALESCE(o.titulo, '') ILIKE '%' || :q || '%'
                    OR a.instrumentacao ILIKE '%' || :q || '%'
                    OR COALESCE(mc.first_name || ' ' || mc.last_name, o.compositor_nome, '') ILIKE '%' || :q || '%'
                ))
              AND (:compositor IS NULL OR
                    COALESCE(mc.first_name || ' ' || mc.last_name, o.compositor_nome, '') ILIKE '%' || :compositor || '%')
              AND (:arranjador IS NULL OR
                    COALESCE(ma.first_name || ' ' || ma.last_name, a.arranjador_nome, '') ILIKE '%' || :arranjador || '%')
              AND (:instrumento IS NULL OR
                    a.instrumentacao ILIKE '%' || :instrumento || '%')
            ORDER BY COALESCE(o.titulo, 'ZZZ'), a.id
            LIMIT 100
        """), {
            "q":           q.strip() or None,
            "compositor":  compositor.strip() or None,
            "arranjador":  arranjador.strip() or None,
            "instrumento": instrumento.strip() or None,
        }).fetchall()

    ctx = make_ctx(request, {
        "resultados":        resultados,
        "q":                 q,
        "filtro_compositor": compositor,
        "filtro_arranjador": arranjador,
        "filtro_instrumento":instrumento,
        "copyright_labels":  COPYRIGHT_LABELS,
        "genero_labels":     GENERO_LABELS,
    })
    resp = templates.TemplateResponse("acervo/busca.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])


# ══════════════════════════════════════════════════════════════
# HISTÓRICO DE EXECUÇÕES
# ══════════════════════════════════════════════════════════════

@router.get("/historico", response_class=HTMLResponse)
def historico(request: Request, db: Session = Depends(get_db)):
    top_mais = db.execute(text("""
        SELECT o.titulo, COUNT(ca.id) AS total
        FROM concerto_arranjos ca
        JOIN arranjos a ON a.id = ca.arranjo_id
        JOIN obras    o ON o.id = a.obra_id
        WHERE ca.data_execucao IS NOT NULL
        GROUP BY o.id, o.titulo
        ORDER BY total DESC LIMIT 10
    """)).fetchall()

    top_menos = db.execute(text("""
        SELECT o.titulo, COUNT(ca.id) AS total
        FROM obras o
        JOIN arranjos a ON a.obra_id = o.id AND a.ativo = TRUE
        LEFT JOIN concerto_arranjos ca ON ca.arranjo_id = a.id AND ca.data_execucao IS NOT NULL
        GROUP BY o.id, o.titulo
        ORDER BY total ASC, o.titulo LIMIT 10
    """)).fetchall()

    top_repetidas = db.execute(text("""
        SELECT o.titulo,
               COALESCE(a.titulo_arranjo, 'Arranjo principal') AS arranjo,
               COUNT(ca.id) AS total
        FROM concerto_arranjos ca
        JOIN arranjos a ON a.id = ca.arranjo_id
        JOIN obras    o ON o.id = a.obra_id
        WHERE ca.data_execucao IS NOT NULL
        GROUP BY a.id, o.titulo, a.titulo_arranjo
        ORDER BY total DESC LIMIT 10
    """)).fetchall()

    ctx = make_ctx(request, {
        "top_mais":      top_mais,
        "top_menos":     top_menos,
        "top_repetidas": top_repetidas,
    })
    resp = templates.TemplateResponse("acervo/historico.html", ctx)
    return set_lang_cookie(resp, ctx["lang"])
