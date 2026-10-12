"""P0 health + request_id + auditoria básica."""
from app.audit import clamp_retention_days, should_auto_audit, summarize_http, AUDIT_RETENTION_MIN, AUDIT_RETENTION_MAX


def test_retention_clamp():
    assert clamp_retention_days(1) == AUDIT_RETENTION_MIN
    assert clamp_retention_days(999) == AUDIT_RETENTION_MAX
    assert clamp_retention_days(30) == 30
    assert clamp_retention_days(None) == 90


def test_should_auto_audit():
    assert should_auto_audit("POST", "/musicians/1/delete") is True
    assert should_auto_audit("GET", "/musicians/") is False
    assert should_auto_audit("POST", "/login") is False
    assert should_auto_audit("POST", "/healthz") is False
    assert should_auto_audit("POST", "/static/x") is False


def test_summarize_http():
    action, etype, eid, summary = summarize_http("POST", "/musicians/42/delete", 303)
    assert action.startswith("post.")
    assert etype == "musicians"
    assert eid == "42"
    assert "303" in summary
