"""
Portal — Lógica de distribuição de partituras para eventos.
Associa partes do acervo aos músicos e gera links de acesso.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import (
    ArranjoDocumento, Concerto, ConcertoAcessoPartitura,
    ConcertoDocumento, InstrumentoBase, Musician, member_instruments_table,
)


def _normalizar_instrumento(nome: str) -> str:
    return nome.lower().strip().replace("  ", " ")


def _musico_toca_instrumento(musician: Musician, instrumento_nome: str) -> bool:
    """Verifica se o músico toca o instrumento da parte (match flexível)."""
    alvo = _normalizar_instrumento(instrumento_nome)
    for inst in musician.instruments:
        nome = _normalizar_instrumento(inst.nome)
        if alvo in nome or nome in alvo:
            return True
        # "Violino 1" ↔ "Violino"
        base_alvo = alvo.split()[0] if alvo else ""
        base_nome = nome.split()[0] if nome else ""
        if base_alvo and base_nome and base_alvo == base_nome:
            return True
    return False


def _add_atribuicao(
    atribuicoes: dict[int, dict],
    musician: Musician,
    doc: ArranjoDocumento,
    obra_titulo: str,
) -> None:
    if musician.id not in atribuicoes:
        atribuicoes[musician.id] = {
            "musician": musician,
            "documentos": [],
            "obras": set(),
        }
    if doc.id not in [d.id for d in atribuicoes[musician.id]["documentos"]]:
        atribuicoes[musician.id]["documentos"].append(doc)
        atribuicoes[musician.id]["obras"].add(obra_titulo)


def _maestros_do_evento(db: Session, evento: Concerto) -> list[Musician]:
    """Maestro do evento, se ativo; senão maestros ativos do cadastro."""
    from app.models import MemberRole, RoleType

    if evento.maestro_id:
        m = (
            db.query(Musician)
            .filter(Musician.id == evento.maestro_id, Musician.is_active == True)
            .first()
        )
        if m:
            return [m]
    return (
        db.query(Musician)
        .filter(
            Musician.is_active == True,
            Musician.roles.any(MemberRole.role_type == RoleType.maestro),
        )
        .order_by(Musician.first_name, Musician.last_name)
        .all()
    )


def sugerir_distribuicao(db: Session, evento: Concerto) -> list[dict]:
    """
    Sugere quais partituras cada músico deve receber com base no programa
    e nos instrumentos cadastrados. A grade vai para o maestro do evento.

    Retorna lista de dicts:
    {musician, documentos: [ArranjoDocumento], obra_titulo}
    """
    atribuicoes: dict[int, dict] = {}

    for ca in evento.programa:
        arranjo = ca.arranjo
        obra_titulo = arranjo.obra.titulo if arranjo.obra else (arranjo.titulo_arranjo or "Arranjo")

        for doc in arranjo.documentos:
            if doc.tipo == "grade":
                for maestro in _maestros_do_evento(db, evento):
                    _add_atribuicao(atribuicoes, maestro, doc, obra_titulo)
                continue

            candidatos: list[Musician] = []
            if doc.tipo == "instrumento" and doc.instrumento_nome:
                musicos = (
                    db.query(Musician)
                    .filter(Musician.is_active == True)
                    .all()
                )
                candidatos = [m for m in musicos if _musico_toca_instrumento(m, doc.instrumento_nome)]

            elif doc.tipo == "coral" and doc.stab_tipo:
                from app.models import MemberRole, RoleType, VoiceType
                voz_map = {
                    "soprano": VoiceType.soprano,
                    "alto": VoiceType.alto,
                    "tenor": VoiceType.tenor,
                    "baixo": VoiceType.baixo,
                }
                voz = voz_map.get(doc.stab_tipo)
                if voz:
                    candidatos = (
                        db.query(Musician)
                        .filter(
                            Musician.is_active == True,
                            Musician.roles.any(
                                (MemberRole.role_type == RoleType.cantor) &
                                (MemberRole.voice_type == voz)
                            ),
                        )
                        .all()
                    )
                elif doc.stab_tipo == "completo":
                    candidatos = (
                        db.query(Musician)
                        .filter(
                            Musician.is_active == True,
                            Musician.roles.any(MemberRole.role_type == RoleType.cantor),
                        )
                        .all()
                    )

            for m in candidatos:
                _add_atribuicao(atribuicoes, m, doc, obra_titulo)

    resultado = []
    for data in atribuicoes.values():
        if data["documentos"]:
            resultado.append({
                "musician": data["musician"],
                "documentos": data["documentos"],
                "obras": sorted(data["obras"]),
            })

    resultado.sort(key=lambda x: x["musician"].full_name)
    return resultado


def calcular_valid_from(evento: Concerto) -> datetime:
    """Início do dia UTC da data de início do evento."""
    base = evento.data_inicio
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def calcular_expiracao(evento: Concerto) -> datetime:
    """Link válido até 1 dia após o evento."""
    base = evento.data_fim or evento.data_inicio
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    return base + timedelta(days=1)


def criar_ou_atualizar_acessos(
    db: Session,
    evento: Concerto,
    atribuicoes: list[dict],
) -> list[ConcertoAcessoPartitura]:
    """
    Cria/atualiza tokens de acesso e registros em concerto_documentos.

    atribuicoes: [{musician_id, documento_ids: [int]}]
    """
    valid_from = calcular_valid_from(evento)
    expires = calcular_expiracao(evento)
    acessos: list[ConcertoAcessoPartitura] = []
    # Evita UniqueViolation quando o mesmo documento vai para vários músicos
    # no mesmo flush (query ainda não vê inserts pendentes).
    docs_cache: dict[int, ConcertoDocumento] = {}

    for item in atribuicoes:
        musician_id = item["musician_id"]
        doc_ids = item.get("documento_ids", [])
        if not doc_ids:
            continue

        acesso = (
            db.query(ConcertoAcessoPartitura)
            .filter_by(concerto_id=evento.id, musician_id=musician_id)
            .first()
        )
        if acesso:
            acesso.documento_ids = doc_ids
            acesso.valid_from = valid_from
            acesso.expires_at = expires
        else:
            acesso = ConcertoAcessoPartitura(
                concerto_id=evento.id,
                musician_id=musician_id,
                documento_ids=doc_ids,
                valid_from=valid_from,
                expires_at=expires,
            )
            db.add(acesso)

        for doc_id in doc_ids:
            doc = db.query(ArranjoDocumento).filter_by(id=doc_id).first()
            if not doc:
                continue
            existing = docs_cache.get(doc_id)
            if existing is None:
                existing = (
                    db.query(ConcertoDocumento)
                    .filter_by(concerto_id=evento.id, arranjo_documento_id=doc_id)
                    .first()
                )
            if not existing:
                existing = ConcertoDocumento(
                    concerto_id=evento.id,
                    arranjo_documento_id=doc_id,
                    instrumento_executando=doc.instrumento_nome or doc.stab_tipo or doc.tipo,
                    musicos_ids=[musician_id],
                )
                db.add(existing)
            else:
                ids = list(existing.musicos_ids or [])
                if musician_id not in ids:
                    existing.musicos_ids = ids + [musician_id]
            docs_cache[doc_id] = existing

        acessos.append(acesso)

    db.flush()
    return acessos
