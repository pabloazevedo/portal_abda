"""
Testes de Regressão - Fase 1: Migrations + Modelos + Novos Módulos

Executar com:
  docker compose exec app pytest tests/test_regression_fase1.py -v
"""

import pytest
from sqlalchemy.orm import Session
from app.database import SessionLocal, Base, engine
from app.models import (
    Obra,
    Arranjo,
    Musician,
    User,
    InstrumentoBase,
    ArranjoDocumento,
    TipoDocumento,
    CompartilhamentoArranjo,
    Compositor,
    UserRole,
    RoleType,
)


# ──────────────────────────────────────────────────────────────────
# TESTES DE BANCO DE DADOS
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
def db():
    """Fixture: Sessão de DB para testes."""
    # Criar tabelas (em teste)
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    yield session
    session.close()

    # Limpar após teste
    Base.metadata.drop_all(bind=engine)


def test_migration_arranjo_documentos_exists(db: Session):
    """Verificar se tabela arranjo_documentos foi criada."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "arranjo_documentos" in tables, "Tabela arranjo_documentos não existe"


def test_migration_compartilhamento_exists(db: Session):
    """Verificar se tabela compartilhamento_arranjos foi criada."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "compartilhamento_arranjos" in tables, "Tabela compartilhamento_arranjos não existe"


def test_migration_auditoria_compartilhamento_exists(db: Session):
    """Verificar se tabela auditoria_compartilhamento foi criada."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "auditoria_compartilhamento" in tables, "Tabela auditoria_compartilhamento não existe"


def test_migration_auditoria_validacao_exists(db: Session):
    """Verificar se tabela auditoria_validacao_documento foi criada."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert (
        "auditoria_validacao_documento" in tables
    ), "Tabela auditoria_validacao_documento não existe"


def test_migration_compositores_exists(db: Session):
    """Verificar se tabela compositores foi criada."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    assert "compositores" in tables, "Tabela compositores não existe"


# ──────────────────────────────────────────────────────────────────
# TESTES DE MODELOS ORM
# ──────────────────────────────────────────────────────────────────


def test_criar_arranjo_documento(db: Session):
    """Criar ArranjoDocumento funciona."""
    # Setup
    user = User(username="test", email="test@example.com", password_hash="xxx", role=UserRole.admin)
    db.add(user)
    db.commit()

    obra = Obra(titulo="Test", compositor_nome="Test", created_by=user.id)
    db.add(obra)
    db.commit()

    arranjo = Arranjo(
        obra_id=obra.id,
        instrumentacao="Test",
        copyright_status="dominio_publico",
        created_by=user.id,
    )
    db.add(arranjo)
    db.commit()

    # Create
    doc = ArranjoDocumento(
        arranjo_id=arranjo.id,
        tipo=TipoDocumento.grade,
        versao="v1.0",
        arquivo_s3_key="obras/arranjo_1/grade/v1.0/test.pdf",
        tamanho_bytes=1024,
        created_by=user.id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Assert
    assert doc.id is not None
    assert doc.tipo == TipoDocumento.grade
    assert doc.ativo is True


def test_compartilhamento_arranjo_relationship(db: Session):
    """Relacionamento CompartilhamentoArranjo funciona."""
    # Setup
    user = User(username="test", email="test@example.com", password_hash="xxx", role=UserRole.admin)
    db.add(user)
    db.commit()

    obra = Obra(titulo="Test", compositor_nome="Test", created_by=user.id)
    db.add(obra)
    db.commit()

    arranjo = Arranjo(
        obra_id=obra.id,
        instrumentacao="Test",
        copyright_status="dominio_publico",
        created_by=user.id,
    )
    db.add(arranjo)
    db.commit()

    doc = ArranjoDocumento(
        arranjo_id=arranjo.id,
        tipo=TipoDocumento.grade,
        arquivo_s3_key="obras/arranjo_1/grade/v1.0/test.pdf",
        created_by=user.id,
    )
    db.add(doc)
    db.commit()

    # Create compartilhamento
    compartilhamento = CompartilhamentoArranjo(
        arranjo_documento_id=doc.id,
        token_acesso="test-token-123",
        criado_por=user.id,
    )
    db.add(compartilhamento)
    db.commit()
    db.refresh(compartilhamento)

    # Assert
    assert compartilhamento.id is not None
    assert compartilhamento.documento.id == doc.id
    assert compartilhamento.status.value == "ativo"


def test_compositor_seed_data(db: Session):
    """Dados de seed de compositores foram criados."""
    compositores = db.query(Compositor).all()

    assert len(compositores) > 0, "Nenhum compositor foi seedado"
    assert any(c.nome_completo == "Wolfgang Amadeus Mozart" for c in compositores)


# ──────────────────────────────────────────────────────────────────
# TESTES DE REGRESSÃO (Funcionalidade Existente Não Quebrou)
# ──────────────────────────────────────────────────────────────────


def test_criar_obra_ainda_funciona(db: Session):
    """Criar Obra ainda funciona (não quebrou com novas migrations)."""
    user = User(username="test", email="test@example.com", password_hash="xxx", role=UserRole.admin)
    db.add(user)
    db.commit()

    obra = Obra(
        titulo="Sinfonia 40",
        compositor_nome="W.A. Mozart",
        created_by=user.id,
    )
    db.add(obra)
    db.commit()
    db.refresh(obra)

    assert obra.id is not None
    assert obra.titulo == "Sinfonia 40"


def test_criar_arranjo_ainda_funciona(db: Session):
    """Criar Arranjo ainda funciona (não quebrou)."""
    user = User(username="test", email="test@example.com", password_hash="xxx", role=UserRole.admin)
    db.add(user)
    db.commit()

    obra = Obra(titulo="Test", compositor_nome="Test", created_by=user.id)
    db.add(obra)
    db.commit()

    arranjo = Arranjo(
        obra_id=obra.id,
        instrumentacao="2 Violinos, Viola, Cello",
        copyright_status="dominio_publico",
        created_by=user.id,
    )
    db.add(arranjo)
    db.commit()
    db.refresh(arranjo)

    assert arranjo.id is not None


def test_arranjo_relacionamento_documentos(db: Session):
    """Arranjo.documentos relacionamento funciona."""
    user = User(username="test", email="test@example.com", password_hash="xxx", role=UserRole.admin)
    db.add(user)
    db.commit()

    obra = Obra(titulo="Test", compositor_nome="Test", created_by=user.id)
    db.add(obra)
    db.commit()

    arranjo = Arranjo(
        obra_id=obra.id,
        instrumentacao="Test",
        copyright_status="dominio_publico",
        created_by=user.id,
    )
    db.add(arranjo)
    db.commit()

    # Adicionar documentos
    doc1 = ArranjoDocumento(
        arranjo_id=arranjo.id,
        tipo=TipoDocumento.grade,
        arquivo_s3_key="obras/arranjo_1/grade/v1.0/grade.pdf",
        created_by=user.id,
    )
    doc2 = ArranjoDocumento(
        arranjo_id=arranjo.id,
        tipo=TipoDocumento.parte_instrumento,
        arquivo_s3_key="obras/arranjo_1/parte/v1.0/violino1.pdf",
        created_by=user.id,
    )
    db.add(doc1)
    db.add(doc2)
    db.commit()

    # Refresh arranjo
    db.refresh(arranjo)

    # Assert
    assert len(arranjo.documentos) == 2
    assert any(d.tipo == TipoDocumento.grade for d in arranjo.documentos)


# ──────────────────────────────────────────────────────────────────
# TESTES DE MÓDULOS BACKEND
# ──────────────────────────────────────────────────────────────────


def test_s3_manager_health_check():
    """S3 manager health check funciona (local mode)."""
    from app.s3_manager import health_check

    result = health_check()
    assert result["status"] in ["ok", "error"]
    assert result["mode"] == "local"


def test_fuzzy_matcher_basic():
    """Fuzzy matcher básico funciona."""
    from app.validators.fuzzy_matcher import fuzzy_match

    score, matched = fuzzy_match("Sinfonia 40", "Symphony No. 40", threshold=75)
    assert matched is True
    assert score >= 75


def test_fuzzy_matcher_composer():
    """Fuzzy matcher de compositor funciona."""
    from app.validators.fuzzy_matcher import fuzzy_match_compositor

    score = fuzzy_match_compositor("W.A. Mozart", "Wolfgang Amadeus Mozart")
    assert score >= 80


def test_metadata_extractor_pdf():
    """Extrator de metadados PDF funciona."""
    from app.extractors.metadata_extractor import extrair_metadados

    # Criar PDF mínimo (válido mas vazio)
    pdf_bytes = b"%PDF-1.4\n"

    resultado = extrair_metadados("test.pdf", pdf_bytes)
    assert resultado.formato == "pdf"
    # Pode ter erro por PDF vazio, mas não deve crashear


def test_documento_validator_completo():
    """Validador completo funciona sem erros."""
    from app.validators.documento_validator import validar_documento_completo

    # PDF mínimo
    pdf_bytes = b"%PDF-1.4\n"

    resultado = validar_documento_completo(
        filename="test.pdf",
        file_bytes=pdf_bytes,
        titulo_cadastro="Test",
        compositor_cadastro="Test",
    )

    assert resultado.status is not None
    assert resultado.score_geral >= 0


# ──────────────────────────────────────────────────────────────────
# Teste Summary
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
