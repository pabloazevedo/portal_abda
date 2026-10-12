"""
Portal — Modelos de dados (SQLAlchemy ORM).
Versão 2.1 — suporte a múltiplos papéis, instrumentos e módulo de patrimônio.
"""

import enum
from datetime import datetime, timezone, timedelta

from sqlalchemy import (
    Boolean, Column, DateTime, Date, Enum, ForeignKey, Index,
    Integer, JSON, Numeric, SmallInteger, String, Table, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────

class MemberType(str, enum.Enum):
    """Legado — mantido para compatibilidade. Usar RoleType nas novas features."""
    orchestra = "orchestra"
    choir     = "choir"
    both      = "both"


class UserRole(str, enum.Enum):
    admin      = "admin"       # Acesso total ao sistema
    maestro    = "maestro"     # Gestão artística e de membros
    arquivista = "arquivista"  # Gestão de patrimônio e acervo
    secretaria = "secretaria"  # Gestão de membros
    user       = "user"        # Somente leitura


class VoiceType(str, enum.Enum):
    """Tipos de voz para cantores (SATB)."""
    soprano = "soprano"
    alto    = "alto"
    tenor   = "tenor"
    baixo   = "baixo"


class RoleType(str, enum.Enum):
    """Papéis que um membro pode assumir (N por membro)."""
    musico      = "musico"        # Músico de orquestra
    maestro     = "maestro"       # Maestro (requer maestro_order)
    chefe_naipe = "chefe_naipe"   # Chefe de Naipe
    arquivista  = "arquivista"    # Arquivista Musical
    arranjador  = "arranjador"    # Arranjador
    cantor      = "cantor"        # Cantor / Corista (requer voice_type)
    compositor  = "compositor"    # Compositor


# ──────────────────────────────────────────────────────────────
# Tabela de associação: Membro ↔ Instrumento (N:N sem dados extra)
# ──────────────────────────────────────────────────────────────

member_instruments_table = Table(
    "member_instruments",
    Base.metadata,
    Column(
        "musician_id",
        Integer,
        ForeignKey("musicians.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "instrumento_id",
        Integer,
        ForeignKey("instrumentos_base.id"),
        primary_key=True,
    ),
)


# ──────────────────────────────────────────────────────────────
# InstrumentoBase — Single Source of Truth
# ──────────────────────────────────────────────────────────────

class InstrumentoBase(Base):
    __tablename__ = "instrumentos_base"

    id         = Column(Integer, primary_key=True, index=True)
    nome       = Column(String(100), nullable=False, unique=True, index=True)
    categoria  = Column(String(80),  nullable=False)
    ativo      = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_now)

    def __repr__(self) -> str:
        return f"<InstrumentoBase id={self.id} nome={self.nome!r}>"


# ──────────────────────────────────────────────────────────────
# MemberRole — papel de um membro (N por membro)
# ──────────────────────────────────────────────────────────────

class MemberRole(Base):
    __tablename__ = "member_roles"
    __table_args__ = (
        UniqueConstraint("musician_id", "role_type", name="uq_member_role"),
    )

    id              = Column(Integer, primary_key=True, index=True)
    musician_id     = Column(Integer, ForeignKey("musicians.id", ondelete="CASCADE"), nullable=False)
    role_type       = Column(Enum(RoleType, name="role_type"), nullable=False)
    # Obrigatório quando role_type == 'maestro'
    maestro_order   = Column(SmallInteger, nullable=True)
    # Obrigatório quando role_type == 'cantor'
    voice_type      = Column(Enum(VoiceType, name="voice_type", native_enum=False), nullable=True)
    created_at      = Column(DateTime, default=_now)

    musician = relationship("Musician", back_populates="roles")

    @property
    def label(self) -> str:
        labels = {
            RoleType.musico:      "Músico",
            RoleType.maestro:     f"{self.maestro_order}º Maestro/Maestrina" if self.maestro_order else "Maestro/Maestrina",
            RoleType.chefe_naipe: "Chefe de Naipe",
            RoleType.arquivista:  "Arquivista",
            RoleType.arranjador:  "Arranjador",
            RoleType.cantor:      f"Coralista ({self.voice_type.value.title()})" if self.voice_type else "Coralista",
            RoleType.compositor:  "Compositor",
        }
        return labels.get(self.role_type, self.role_type.value)

    def __repr__(self) -> str:
        return f"<MemberRole musician_id={self.musician_id} role={self.role_type.value}>"


# ──────────────────────────────────────────────────────────────
# Musician — membro da orquestra / coral
# ──────────────────────────────────────────────────────────────

class Musician(Base):
    __tablename__ = "musicians"

    id         = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name  = Column(String(100), nullable=False)
    apelido    = Column(String(100), nullable=True)
    celular    = Column(String(20),  nullable=False, server_default="")   # obrigatório (I-01)
    telefone   = Column(String(20),  nullable=True)   # opcional
    phone      = Column(String(30),  nullable=True)   # deprecated — mantido para dados legados
    email      = Column(String(150), nullable=False, unique=True, index=True)
    birth_date = Column(Date, nullable=False)
    photo      = Column(String(255), nullable=True)
    is_active  = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    # ── Campos legados (mantidos para retrocompatibilidade) ──
    member_type = Column(Enum(MemberType), nullable=True)  # deprecated
    instrument  = Column(String(100), nullable=True)        # deprecated
    voice       = Column(String(50),  nullable=True)        # deprecated

    # ── Novas relações ───────────────────────────────────────
    roles = relationship(
        "MemberRole",
        back_populates="musician",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="MemberRole.role_type",
    )
    instruments = relationship(
        "InstrumentoBase",
        secondary=member_instruments_table,
        lazy="selectin",
        order_by="InstrumentoBase.categoria, InstrumentoBase.nome",
    )

    # ── Propriedades de conveniência ─────────────────────────
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self) -> int:
        today = datetime.today().date()
        bd = self.birth_date
        return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))

    @property
    def role_labels(self) -> list[str]:
        return [r.label for r in self.roles]

    @property
    def instrument_names(self) -> list[str]:
        return [i.nome for i in self.instruments]

    def __repr__(self) -> str:
        return f"<Musician id={self.id} name={self.full_name!r}>"


# ──────────────────────────────────────────────────────────────
# User — usuário do sistema (acesso ao painel)
# ──────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String(50),  unique=True, nullable=False, index=True)
    email         = Column(String(150), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role          = Column(Enum(UserRole), default=UserRole.user, nullable=False)
    is_active     = Column(Boolean, default=True, nullable=False)
    created_at    = Column(DateTime, default=_now)
    # Vínculo opcional com membro (app mobile de partituras)
    musician_id   = Column(Integer, ForeignKey("musicians.id", ondelete="SET NULL"), nullable=True, unique=True, index=True)

    musician = relationship("Musician", foreign_keys=[musician_id], lazy="selectin")

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role.value}>"


class ApiRefreshToken(Base):
    """Refresh token opaco para apps mobile (Android/iOS)."""
    __tablename__ = "api_refresh_tokens"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    user_agent = Column(String(255), nullable=True)
    client     = Column(String(40), nullable=True)  # android | ios | other

    user = relationship("User")

    def __repr__(self) -> str:
        return f"<ApiRefreshToken user_id={self.user_id}>"


# ──────────────────────────────────────────────────────────────
# PasswordResetToken — token de recuperação de senha (uso único)
# ──────────────────────────────────────────────────────────────

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id         = Column(Integer, primary_key=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False)
    used_at    = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=_now)

    user = relationship("User")

    def __repr__(self) -> str:
        return f"<PasswordResetToken user_id={self.user_id} expires={self.expires_at}>"


# ──────────────────────────────────────────────────────────────
# Enums — Módulo de Patrimônio
# ──────────────────────────────────────────────────────────────

class TipoItem(str, enum.Enum):
    Instrumento = "Instrumento"
    Movel       = "Movel"
    Eletronico  = "Eletronico"
    Partitura   = "Partitura"
    Decoracao   = "Decoracao"
    Outros      = "Outros"


class StatusPatrimonio(str, enum.Enum):
    Disponivel  = "Disponivel"
    Emprestado  = "Emprestado"
    Manutencao  = "Manutencao"
    Baixa       = "Baixa"


class EtiquetaTipo(str, enum.Enum):
    qr          = "qr"
    barcode_1d  = "barcode_1d"
    data_matrix = "data_matrix"
    rfid_hf     = "rfid_hf"
    rfid_uhf    = "rfid_uhf"


# ──────────────────────────────────────────────────────────────
# Patrimônio — ativo do inventário
# ──────────────────────────────────────────────────────────────

class Patrimonio(Base):
    __tablename__ = "patrimonio"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    tipo_item             = Column(Enum(TipoItem,          name="tipo_item_enum"),             nullable=False)
    status                = Column(Enum(StatusPatrimonio,  name="status_patrimonio_enum"),      nullable=False, default=StatusPatrimonio.Disponivel)
    identificador_interno = Column(String(50),  nullable=False, unique=True, index=True)
    qr_payload            = Column(String(512), nullable=True)
    barcode_value         = Column(String(64),  nullable=True, index=True)
    fabricante            = Column(String(200), nullable=True)
    modelo                = Column(String(200), nullable=True)
    ano_compra            = Column(SmallInteger, nullable=True)
    valor_mercado         = Column(Numeric(12, 2), nullable=True)
    detalhes              = Column(JSONB, nullable=True)
    observacoes           = Column(Text,  nullable=True)
    created_at            = Column(DateTime, default=_now)
    updated_at            = Column(DateTime, default=_now, onupdate=_now)

    emprestimos = relationship(
        "PatrimonioEmprestimo",
        back_populates="patrimonio",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PatrimonioEmprestimo.data_emprestimo.desc()",
    )
    etiquetas = relationship(
        "PatrimonioEtiqueta",
        back_populates="patrimonio",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="PatrimonioEtiqueta.created_at",
    )

    @property
    def emprestimo_ativo(self):
        """Retorna o empréstimo em aberto (sem devolução), ou None."""
        for e in self.emprestimos:
            if e.data_devolucao is None:
                return e
        return None

    @property
    def tipo_label(self) -> str:
        from app.labels import TIPO_LABEL
        return TIPO_LABEL.get(self.tipo_item, self.tipo_item.value)

    @property
    def status_label(self) -> str:
        from app.labels import STATUS_LABEL
        return STATUS_LABEL.get(self.status, self.status.value)

    def __repr__(self) -> str:
        return f"<Patrimonio id={self.id} tipo={self.tipo_item.value} id_interno={self.identificador_interno!r}>"


# ──────────────────────────────────────────────────────────────
# PatrimonioEmprestimo — vínculo item ↔ músico
# ──────────────────────────────────────────────────────────────

class PatrimonioEmprestimo(Base):
    __tablename__ = "patrimonio_emprestimo"

    id              = Column(Integer, primary_key=True, index=True)
    patrimonio_id   = Column(UUID(as_uuid=True), ForeignKey("patrimonio.id", ondelete="CASCADE"), nullable=False)
    musician_id     = Column(Integer,             ForeignKey("musicians.id",  ondelete="CASCADE"), nullable=False)
    data_emprestimo = Column(DateTime, nullable=False, default=_now)
    data_devolucao  = Column(DateTime, nullable=True)
    observacoes     = Column(Text, nullable=True)
    created_at      = Column(DateTime, default=_now)

    patrimonio = relationship("Patrimonio",  back_populates="emprestimos")
    musician   = relationship("Musician",    lazy="selectin")

    def __repr__(self) -> str:
        return f"<PatrimonioEmprestimo pat={self.patrimonio_id} musician={self.musician_id} devolvido={self.data_devolucao is not None}>"


# ──────────────────────────────────────────────────────────────
# PatrimonioEtiqueta — vínculo item ↔ etiqueta física
# ──────────────────────────────────────────────────────────────

class PatrimonioEtiqueta(Base):
    __tablename__ = "patrimonio_etiqueta"
    __table_args__ = (
        UniqueConstraint("tipo", "valor", name="uq_etiqueta_valor"),
    )

    id            = Column(Integer, primary_key=True, index=True)
    patrimonio_id = Column(UUID(as_uuid=True), ForeignKey("patrimonio.id", ondelete="CASCADE"), nullable=False)
    tipo          = Column(Enum(EtiquetaTipo, name="etiqueta_tipo_enum"), nullable=False)
    valor         = Column(String(255), nullable=False, index=True)
    ativo         = Column(Boolean, default=True, nullable=False)
    created_at    = Column(DateTime, default=_now)

    patrimonio = relationship("Patrimonio", back_populates="etiquetas")

    def __repr__(self) -> str:
        return f"<PatrimonioEtiqueta tipo={self.tipo.value} valor={self.valor!r} ativo={self.ativo}>"


# ──────────────────────────────────────────────────────────────
# PatrimonioAuditoria — log imutável de eventos (append-only)
# ──────────────────────────────────────────────────────────────

class PatrimonioAuditoria(Base):
    __tablename__ = "patrimonio_auditoria"

    id            = Column(Integer, primary_key=True, index=True)
    patrimonio_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    acao          = Column(String(50), nullable=False)
    usuario_id    = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    payload       = Column(JSONB, nullable=False, default=dict)
    created_at    = Column(DateTime, default=_now)

    def __repr__(self) -> str:
        return f"<PatrimonioAuditoria pat={self.patrimonio_id} acao={self.acao!r}>"


# ──────────────────────────────────────────────────────────────
# Configuracao — tabela singleton (id = 1) para dados do rodapé
# ──────────────────────────────────────────────────────────────

class Configuracao(Base):
    __tablename__ = "configuracoes"

    id                 = Column(Integer, primary_key=True, default=1)
    nome_institucional = Column(String(200), nullable=False, default="")
    endereco           = Column(Text, nullable=False, default="")
    link_estatuto      = Column(String(500), nullable=False, default="")
    link_repositorio   = Column(String(500), nullable=False, default="")
    # Idioma da aplicação (global) — apenas admin altera via Configurações
    idioma             = Column(String(5), nullable=False, default="pt", server_default="pt")
    # Retenção de logs de auditoria (dias) — min 7, max 90
    audit_retention_days = Column(Integer, nullable=False, default=90, server_default="90")
    # Site mobile / PWA (/m) — admin liga/desliga em Configurações → Sistema
    pwa_enabled = Column(Boolean, nullable=False, default=False, server_default="false")

    def to_dict(self) -> dict:
        lang = (self.idioma or "pt").strip().lower()
        if lang not in {"pt", "en", "es"}:
            lang = "pt"
        try:
            retention = int(self.audit_retention_days or 90)
        except (TypeError, ValueError):
            retention = 90
        retention = max(7, min(90, retention))
        return {
            "nome_institucional": self.nome_institucional or "",
            "endereco":           self.endereco or "",
            "link_estatuto":      self.link_estatuto or "",
            "link_repositorio":   self.link_repositorio or "",
            "idioma":             lang,
            "audit_retention_days": retention,
            "pwa_enabled":        bool(self.pwa_enabled),
        }


class WhatsAppGrupo(Base):
    """Grupo de WhatsApp por naipe (orquestra) ou naipe vocal (coral) para envio do link PWA."""
    __tablename__ = "whatsapp_grupos"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    codigo        = Column(String(64), nullable=False, unique=True, index=True)
    nome          = Column(String(120), nullable=False)
    tipo          = Column(String(32), nullable=False, default="orquestra")  # orquestra | coral | geral
    whatsapp_url  = Column(String(500), nullable=True)  # chat.whatsapp.com/... ou vazio
    telefone      = Column(String(20), nullable=True)   # opcional: wa.me/<fone>
    ordem         = Column(Integer, nullable=False, default=0)
    ativo         = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at    = Column(DateTime, default=_now)
    updated_at    = Column(DateTime, default=_now, onupdate=_now)

    def __repr__(self) -> str:
        return f"<WhatsAppGrupo codigo={self.codigo!r} nome={self.nome!r}>"


class AuditLog(Base):
    """Registro de auditoria: quem fez o quê."""
    __tablename__ = "audit_logs"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    created_at      = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    actor_user_id   = Column(Integer, nullable=True, index=True)
    actor_username  = Column(String(100), nullable=True)
    action          = Column(String(80), nullable=False, index=True)
    entity_type     = Column(String(80), nullable=True, index=True)
    entity_id       = Column(String(80), nullable=True)
    summary         = Column(String(500), nullable=True)
    ip              = Column(String(64), nullable=True)
    request_id      = Column(String(64), nullable=True)
    meta_json       = Column(Text, nullable=True)


class ReleaseNote(Base):
    """Histórico de versões / release notes do portal."""
    __tablename__ = "release_notes"
    __table_args__ = (
        Index("ix_release_notes_released_at", "released_at"),
    )

    id          = Column(Integer, primary_key=True, autoincrement=True)
    version     = Column(String(32), nullable=False, unique=True, index=True)
    title       = Column(String(200), nullable=False, default="")
    notes       = Column(Text, nullable=False, default="")
    released_at = Column(Date, nullable=False)
    is_current  = Column(Boolean, nullable=False, default=False, server_default="false")
    created_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at  = Column(DateTime(timezone=True), nullable=False, default=_now, server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now, server_default=func.now())

    def __repr__(self) -> str:
        return f"<ReleaseNote v={self.version} current={self.is_current}>"


# ──────────────────────────────────────────────────────────────
# Enums — Módulo de Acervo Musical
# ──────────────────────────────────────────────────────────────

class GeneroMusical(str, enum.Enum):
    sinfonia      = "sinfonia"
    concerto      = "concerto"
    camara        = "camara"
    coral         = "coral"
    opera         = "opera"
    sacra         = "sacra"
    popular       = "popular"
    folclorica    = "folclorica"
    contemporanea = "contemporanea"
    outro         = "outro"


class CopyrightStatus(str, enum.Enum):
    dominio_publico = "dominio_publico"
    licenciado      = "licenciado"
    pendente        = "pendente"


# ──────────────────────────────────────────────────────────────
# Obra — entidade central do acervo
# ──────────────────────────────────────────────────────────────

class Obra(Base):
    __tablename__ = "obras"

    id              = Column(Integer, primary_key=True, index=True)
    titulo          = Column(String(300), nullable=False, index=True)
    titulo_original = Column(String(300), nullable=True)
    compositor_id   = Column(Integer, ForeignKey("musicians.id", ondelete="SET NULL"), nullable=True)
    compositor_nome = Column(String(200), nullable=True)
    genero          = Column(Enum(GeneroMusical, name="genero_musical_enum"), nullable=False, default=GeneroMusical.outro)
    tonalidade      = Column(String(20),  nullable=True)
    ano_composicao  = Column(SmallInteger, nullable=True)
    observacoes     = Column(Text, nullable=True)
    created_by      = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at      = Column(DateTime, default=_now)
    updated_at      = Column(DateTime, default=_now, onupdate=_now)

    compositor = relationship("Musician", foreign_keys=[compositor_id], lazy="selectin")
    arranjos   = relationship(
        "Arranjo",
        back_populates="obra",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Arranjo.id",
    )

    @property
    def compositor_label(self) -> str:
        if self.compositor:
            return self.compositor.full_name
        return self.compositor_nome or "—"

    def __repr__(self) -> str:
        return f"<Obra id={self.id} titulo={self.titulo!r}>"


# ──────────────────────────────────────────────────────────────
# Arranjo — versão específica de uma obra
# ──────────────────────────────────────────────────────────────

class Arranjo(Base):
    __tablename__ = "arranjos"

    id                = Column(Integer, primary_key=True, index=True)
    obra_id           = Column(Integer, ForeignKey("obras.id", ondelete="SET NULL"), nullable=True)
    titulo_arranjo    = Column(String(300), nullable=True)
    arranjador_id     = Column(Integer, ForeignKey("musicians.id", ondelete="SET NULL"), nullable=True)
    arranjador_nome   = Column(String(200), nullable=True)
    instrumentacao    = Column(Text, nullable=False)
    duracao_segundos  = Column(Integer, nullable=True)
    editora           = Column(String(200), nullable=True)
    copyright_status  = Column(Enum(CopyrightStatus, name="copyright_status_enum"), nullable=False, default=CopyrightStatus.pendente)
    numero_licenca    = Column(String(100), nullable=True)
    arquivo_partitura = Column(String(500), nullable=True)
    patrimonio_id     = Column(UUID(as_uuid=True), ForeignKey("patrimonio.id", ondelete="SET NULL"), nullable=True)
    ativo             = Column(Boolean, default=True, nullable=False)
    created_by        = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at        = Column(DateTime, default=_now)
    updated_at        = Column(DateTime, default=_now, onupdate=_now)

    obra       = relationship("Obra",     back_populates="arranjos", foreign_keys=[obra_id])
    arranjador = relationship("Musician", foreign_keys=[arranjador_id], lazy="selectin")
    documentos = relationship(
        "ArranjoDocumento",
        back_populates="arranjo",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ArranjoDocumento.tipo",
    )

    @property
    def arranjador_label(self) -> str:
        if self.arranjador:
            return self.arranjador.full_name
        return self.arranjador_nome or "—"

    @property
    def duracao_label(self) -> str:
        if not self.duracao_segundos:
            return "—"
        m, s = divmod(self.duracao_segundos, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}h {m:02d}min {s:02d}s"
        return f"{m}min {s:02d}s"

    def __repr__(self) -> str:
        return f"<Arranjo id={self.id} obra_id={self.obra_id}>"


# ──────────────────────────────────────────────────────────────
# Concerto — evento musical
# ──────────────────────────────────────────────────────────────

class Concerto(Base):
    __tablename__ = "concertos"

    id          = Column(Integer, primary_key=True, index=True)
    titulo      = Column(String(300), nullable=False)
    data_inicio = Column(DateTime(timezone=True), nullable=False)
    data_fim    = Column(DateTime(timezone=True), nullable=True)
    local       = Column(String(300), nullable=True)
    maestro_id  = Column(Integer, ForeignKey("musicians.id", ondelete="SET NULL"), nullable=True)
    descricao   = Column(Text, nullable=True)
    publico     = Column(Boolean, default=True, nullable=False)
    cal_uid     = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    created_by  = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at  = Column(DateTime, default=_now)
    updated_at  = Column(DateTime, default=_now, onupdate=_now)

    maestro  = relationship("Musician", foreign_keys=[maestro_id], lazy="selectin")
    programa = relationship(
        "ConcertoArranjo",
        back_populates="concerto",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ConcertoArranjo.ordem, ConcertoArranjo.id",
    )
    documentos_distribuicao = relationship(
        "ConcertoDocumento",
        back_populates="concerto",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    acessos_partituras = relationship(
        "ConcertoAcessoPartitura",
        back_populates="concerto",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Concerto id={self.id} titulo={self.titulo!r}>"


# ──────────────────────────────────────────────────────────────
# ConcertoArranjo — programa do concerto + registro de execução
# ──────────────────────────────────────────────────────────────

class ConcertoArranjo(Base):
    __tablename__ = "concerto_arranjos"
    __table_args__ = (
        UniqueConstraint("concerto_id", "arranjo_id", name="uq_concerto_arranjo"),
    )

    id             = Column(Integer, primary_key=True, index=True)
    concerto_id    = Column(Integer, ForeignKey("concertos.id", ondelete="CASCADE"), nullable=False)
    arranjo_id     = Column(Integer, ForeignKey("arranjos.id",  ondelete="RESTRICT"), nullable=False)
    ordem          = Column(SmallInteger, nullable=True)
    data_execucao  = Column(DateTime(timezone=True), nullable=True)
    duracao_real_s = Column(Integer, nullable=True)
    observacoes    = Column(Text, nullable=True)
    created_at     = Column(DateTime, default=_now)

    concerto = relationship("Concerto", back_populates="programa")
    arranjo  = relationship("Arranjo",  lazy="selectin")


# ──────────────────────────────────────────────────────────────
# ArranjoDocumento — Arquivo (grade, parte, etc) de um arranjo
# ──────────────────────────────────────────────────────────────

class ArranjoDocumento(Base):
    __tablename__ = "arranjo_documentos"

    id                = Column(Integer, primary_key=True, index=True)
    arranjo_id        = Column(Integer, ForeignKey("arranjos.id", ondelete="CASCADE"), nullable=False)
    tipo              = Column(String(50), nullable=False)  # "grade", "instrumento", "coral", "acompanhamento"
    instrumento_nome  = Column(String(100), nullable=True)  # ex: "Violino 1", "Soprano"
    stab_tipo         = Column(String(20), nullable=True)  # "soprano", "alto", "tenor", "baixo", "completo" (para tipo="coral")
    arquivo_caminho   = Column(String(500), nullable=False, index=True)  # ex: "obras/123/grade/score.pdf"
    tamanho_bytes     = Column(Integer, nullable=True)
    created_by        = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at        = Column(DateTime, default=_now)

    arranjo = relationship("Arranjo", back_populates="documentos", lazy="selectin")
    concertos = relationship("ConcertoDocumento", back_populates="documento", cascade="all, delete-orphan")

    @property
    def tipo_label(self) -> str:
        labels = {
            "grade": "Grade",
            "instrumento": "Parte Individual",
            "coral": "Coral",
            "acompanhamento": "Acompanhamento",
        }
        return labels.get(self.tipo, self.tipo)

    def __repr__(self) -> str:
        return f"<ArranjoDocumento id={self.id} arranjo={self.arranjo_id} tipo={self.tipo}>"


# ──────────────────────────────────────────────────────────────
# ConcertoDocumento — Vinculação de Partituras a Eventos
# ──────────────────────────────────────────────────────────────

class ConcertoAcessoPartitura(Base):
    """Link individual para músico acessar partituras de um evento."""
    __tablename__ = "concerto_acesso_partituras"
    __table_args__ = (
        UniqueConstraint("concerto_id", "musician_id", name="uq_concerto_musician_acesso"),
    )

    id            = Column(Integer, primary_key=True, index=True)
    concerto_id   = Column(Integer, ForeignKey("concertos.id", ondelete="CASCADE"), nullable=False)
    musician_id   = Column(Integer, ForeignKey("musicians.id", ondelete="CASCADE"), nullable=False)
    token         = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True)
    documento_ids = Column(JSON, nullable=False, default=list)
    valid_from    = Column(DateTime(timezone=True), nullable=True)
    expires_at    = Column(DateTime(timezone=True), nullable=False)
    enviado_em    = Column(DateTime(timezone=True), nullable=True)
    created_at    = Column(DateTime, default=_now)

    concerto = relationship("Concerto", back_populates="acessos_partituras", lazy="selectin")
    musician = relationship("Musician", lazy="selectin")

    def __repr__(self) -> str:
        return f"<ConcertoAcessoPartitura concerto={self.concerto_id} musician={self.musician_id}>"


class ConcertoDocumento(Base):
    """Vinculação entre Concerto e ArranjoDocumento para distribuição de partituras"""
    __tablename__ = "concerto_documentos"
    __table_args__ = (
        UniqueConstraint("concerto_id", "arranjo_documento_id", name="uq_concerto_documento"),
        Index("idx_concerto_documentos_concerto", "concerto_id"),
        Index("idx_concerto_documentos_documento", "arranjo_documento_id"),
    )

    id                          = Column(Integer, primary_key=True, index=True)
    concerto_id                 = Column(Integer, ForeignKey("concertos.id", ondelete="CASCADE"), nullable=False)
    arranjo_documento_id        = Column(Integer, ForeignKey("arranjo_documentos.id", ondelete="CASCADE"), nullable=False)
    instrumento_executando      = Column(String(100), nullable=True)  # ex: "Violino 1" (redundante, mas útil)
    musicos_ids                 = Column(JSON, nullable=True)  # Lista de musician_id que executam essa parte
    ordem_distribuicao          = Column(SmallInteger, nullable=True)  # Ordem na lista de distribuição
    notas_distribuicao          = Column(Text, nullable=True)  # Ex: "Duas cópias", "Impressão A3"
    created_at                  = Column(DateTime, default=_now)

    concerto = relationship("Concerto", back_populates="documentos_distribuicao", lazy="selectin")
    documento = relationship("ArranjoDocumento", back_populates="concertos", lazy="selectin")

    def __repr__(self) -> str:
        return f"<ConcertoDocumento id={self.id} concerto={self.concerto_id} documento={self.arranjo_documento_id}>"
