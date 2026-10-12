"""
Portal — Utilitário de envio de email para recuperação de senha.
Prioridade das configurações: app_settings (banco) > variáveis de ambiente > padrão.
Sem servidor configurado, registra o link no log (modo dev).
"""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger("uvicorn.error")


def _get(settings: dict, key: str, env_key: str, default: str = "") -> str:
    """Lê do dict de settings, depois env var, depois default."""
    return settings.get(key) or os.getenv(env_key, default)


def send_partituras_evento(
    to_email: str,
    musician_name: str,
    evento_titulo: str,
    evento_data: str,
    access_url: str,
    settings: dict | None = None,
) -> None:
    """Envia email com link de acesso às partituras do evento."""
    cfg = settings or {}
    smtp_host = _get(cfg, "smtp_host", "SMTP_HOST")
    smtp_port = int(_get(cfg, "smtp_port", "SMTP_PORT", "587"))
    smtp_user = _get(cfg, "smtp_user", "SMTP_USER")
    smtp_pass = _get(cfg, "smtp_password", "SMTP_PASSWORD")
    smtp_from = _get(cfg, "smtp_from", "SMTP_FROM", "noreply@localhost")
    use_tls = cfg.get("smtp_tls", True) if cfg else True

    if not smtp_host:
        logger.warning("=" * 60)
        logger.warning("  [Portal] SMTP não configurado — link de partituras:")
        logger.warning(f"  Músico: {musician_name} ({to_email})")
        logger.warning(f"  Evento: {evento_titulo} — {evento_data}")
        logger.warning(f"  {access_url}")
        logger.warning("=" * 60)
        return

    subject = f"Portal — Partituras: {evento_titulo}"
    html = f"""
    <html><body style="font-family:sans-serif;color:#1a1f2e;">
      <h2 style="color:#1A365C;">Partituras do Evento — Portal</h2>
      <p>Olá, <strong>{musician_name}</strong>!</p>
      <p>As partituras do evento <strong>{evento_titulo}</strong>
         ({evento_data}) estão disponíveis no link abaixo.</p>
      <p style="margin:28px 0;">
        <a href="{access_url}"
           style="background:#1A365C;color:#fff;padding:12px 24px;
                  border-radius:8px;text-decoration:none;font-weight:700;">
          Acessar Minhas Partituras
        </a>
      </p>
      <p style="font-size:12px;color:#6c757d;">
        O download fica liberado a partir do dia do evento. Este link é pessoal e expira após o evento.<br/>
        <a href="{access_url}">{access_url}</a>
      </p>
    </body></html>
    """
    plain = (
        f"Partituras — {evento_titulo}\n\n"
        f"Olá, {musician_name}!\n\n"
        f"Acesse suas partituras: {access_url}\n"
    )
    _send(smtp_host, smtp_port, smtp_user, smtp_pass, smtp_from,
          use_tls, to_email, reset_url=None, subject=subject, html=html, plain=plain)


def send_password_reset(to_email: str, token: str, settings: dict | None = None) -> None:
    """
    Envia email com link de redefinição de senha.
    `settings` pode ser `request.app.state.smtp_settings` ou None para usar só env vars.
    Sem SMTP configurado, imprime o link no log (dev mode).
    """
    cfg = settings or {}
    smtp_host = _get(cfg, "smtp_host",     "SMTP_HOST")
    smtp_port = int(_get(cfg, "smtp_port", "SMTP_PORT", "587"))
    smtp_user = _get(cfg, "smtp_user",     "SMTP_USER")
    smtp_pass = _get(cfg, "smtp_password", "SMTP_PASSWORD")
    smtp_from = _get(cfg, "smtp_from",     "SMTP_FROM", "noreply@localhost")
    base_url  = _get(cfg, "app_base_url",  "APP_BASE_URL", "http://localhost:8000")
    use_tls   = cfg.get("smtp_tls", True) if cfg else True

    reset_url = f"{base_url}/reset-password/{token}"

    if not smtp_host:
        logger.warning("=" * 60)
        logger.warning("  [Portal] SMTP não configurado — link de redefinição:")
        logger.warning(f"  {reset_url}")
        logger.warning("=" * 60)
        return

    _send(smtp_host, smtp_port, smtp_user, smtp_pass, smtp_from,
          use_tls, to_email, reset_url)


def send_test_email(to_email: str, settings: dict) -> None:
    """Envia um email de teste com as configurações fornecidas."""
    smtp_host = settings.get("smtp_host", "")
    smtp_port = int(settings.get("smtp_port", 587))
    smtp_user = settings.get("smtp_user", "")
    smtp_pass = settings.get("smtp_password", "")
    smtp_from = settings.get("smtp_from", "noreply@localhost")
    use_tls   = settings.get("smtp_tls", True)

    if not smtp_host:
        raise ValueError("Servidor SMTP não configurado.")

    subject  = "Portal — Email de Teste"
    html     = """
    <html><body style="font-family:sans-serif;color:#1a1f2e;">
      <h2 style="color:#1A365C;">Teste de Email — Portal</h2>
      <p>✅ As configurações de SMTP estão funcionando corretamente.</p>
    </body></html>
    """
    plain = "Teste de Email — Portal\n\nAs configurações de SMTP estão funcionando corretamente."

    _send(smtp_host, smtp_port, smtp_user, smtp_pass, smtp_from,
          use_tls, to_email, reset_url=None, subject=subject, html=html, plain=plain)


def _send(
    host: str, port: int, user: str, password: str,
    from_addr: str, use_tls: bool,
    to_email: str,
    reset_url: str | None = None,
    subject: str = "Portal — Redefinição de Senha",
    html: str | None = None,
    plain: str | None = None,
) -> None:
    if html is None:
        html = f"""
        <html><body style="font-family:sans-serif;color:#1a1f2e;">
          <h2 style="color:#1A365C;">Redefinição de Senha — Portal</h2>
          <p>Recebemos uma solicitação para redefinir sua senha.</p>
          <p>O link abaixo é válido por <strong>1 hora</strong>.</p>
          <p style="margin:28px 0;">
            <a href="{reset_url}"
               style="background:#1A365C;color:#fff;padding:12px 24px;
                      border-radius:8px;text-decoration:none;font-weight:700;">
              Redefinir Senha
            </a>
          </p>
          <p style="font-size:12px;color:#6c757d;">
            Se não foi você, ignore este email.<br/>
            Link: <a href="{reset_url}">{reset_url}</a>
          </p>
        </body></html>
        """
    if plain is None:
        plain = f"Redefinição de Senha — Portal\n\n{reset_url}\n\nSe não foi você, ignore."

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = from_addr
    msg["To"]      = to_email
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html,  "html",  "utf-8"))

    with smtplib.SMTP(host, port, timeout=10) as server:
        server.ehlo()
        if use_tls and port in (587, 465, 25):
            server.starttls()
            server.ehlo()
        if user and password:
            server.login(user, password)
        server.sendmail(from_addr, [to_email], msg.as_string())

    logger.info(f"[Portal] Email enviado para {to_email}")
