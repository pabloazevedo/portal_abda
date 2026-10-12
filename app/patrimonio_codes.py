"""
Geração e renderização de QR Code / código de barras do inventário.

Códigos são atribuídos automaticamente no cadastro do item (nunca manuais).
Imagens PNG servem visualização e impressão em impressoras de etiquetas.
"""

from __future__ import annotations

import io
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Patrimonio, PatrimonioEtiqueta, EtiquetaTipo


def build_qr_payload(item_id: UUID | str) -> str:
    """Caminho estável usado no QR (o front prefixa o origin)."""
    return f"/patrimonio/scan/{item_id}"


def build_barcode_value(identificador_interno: str) -> str:
    """Code128: usa o identificador interno (ex.: INS-202608-0001)."""
    return (identificador_interno or "").strip().upper()


def assign_system_codes(db: Session, item: Patrimonio) -> None:
    """Preenche qr_payload + barcode_value e espelha em patrimonio_etiqueta."""
    item.qr_payload = build_qr_payload(item.id)
    item.barcode_value = build_barcode_value(item.identificador_interno)
    db.flush()

    def _ensure(tipo: EtiquetaTipo, valor: str) -> None:
        # Já ativa com o valor certo
        active = (
            db.query(PatrimonioEtiqueta)
            .filter(
                PatrimonioEtiqueta.patrimonio_id == item.id,
                PatrimonioEtiqueta.tipo == tipo,
                PatrimonioEtiqueta.valor == valor,
                PatrimonioEtiqueta.ativo.is_(True),
            )
            .first()
        )
        if active:
            return

        # Reativa registro existente (mesmo valor) se estiver inativo
        inactive = (
            db.query(PatrimonioEtiqueta)
            .filter(
                PatrimonioEtiqueta.tipo == tipo,
                PatrimonioEtiqueta.valor == valor,
            )
            .first()
        )
        if inactive:
            inactive.patrimonio_id = item.id
            inactive.ativo = True
            db.flush()
            return

        # Desativa outras ativas do mesmo tipo neste item
        db.query(PatrimonioEtiqueta).filter(
            PatrimonioEtiqueta.patrimonio_id == item.id,
            PatrimonioEtiqueta.tipo == tipo,
            PatrimonioEtiqueta.ativo.is_(True),
        ).update({PatrimonioEtiqueta.ativo: False}, synchronize_session=False)

        db.add(PatrimonioEtiqueta(
            patrimonio_id=item.id,
            tipo=tipo,
            valor=valor,
            ativo=True,
        ))

    _ensure(EtiquetaTipo.qr, str(item.id))
    _ensure(EtiquetaTipo.barcode_1d, item.barcode_value)
    db.flush()


def backfill_system_codes(db: Session) -> int:
    """Preenche códigos em itens antigos. Retorna quantidade atualizada."""
    items = db.query(Patrimonio).all()
    n = 0
    for item in items:
        expected_qr = build_qr_payload(item.id)
        expected_bc = build_barcode_value(item.identificador_interno)
        if item.qr_payload == expected_qr and item.barcode_value == expected_bc:
            # Ainda garante etiquetas espelhadas
            assign_system_codes(db, item)
            continue
        assign_system_codes(db, item)
        n += 1
    db.commit()
    return n


def render_qr_png(absolute_url: str, box_size: int = 8, border: int = 2) -> bytes:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M

    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(absolute_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1A365C", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_barcode_png(value: str, module_width: float = 0.4, module_height: float = 20.0) -> bytes:
    from barcode import Code128
    from barcode.writer import ImageWriter

    buf = io.BytesIO()
    writer = ImageWriter()
    code = Code128(value, writer=writer)
    code.write(buf, options={
        "module_width": module_width,
        "module_height": module_height,
        "quiet_zone": 2.0,
        "font_size": 12,
        "text_distance": 4.0,
        "write_text": True,
        "background": "white",
        "foreground": "black",
    })
    return buf.getvalue()
