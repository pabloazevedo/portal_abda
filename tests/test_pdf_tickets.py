"""Tickets PDF para viewer mobile."""
from app.pdf_tickets import consume_pdf_ticket, issue_pdf_ticket


def test_issue_and_consume_memory_ticket():
    ticket, ttl = issue_pdf_ticket(
        path="uploads/obras/x.pdf",
        filename="Saxofone_Baritono.pdf",
        musician_id=9,
        ttl_seconds=120,
    )
    assert ttl == 120
    assert ticket
    row = consume_pdf_ticket(ticket)
    assert row is not None
    assert row.filename == "Saxofone_Baritono.pdf"
    assert row.path == "uploads/obras/x.pdf"
    # reload still valid
    assert consume_pdf_ticket(ticket) is not None


def test_invalid_ticket_returns_none():
    assert consume_pdf_ticket("does-not-exist") is None
