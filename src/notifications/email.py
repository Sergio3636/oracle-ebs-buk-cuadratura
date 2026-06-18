import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from src.config.settings import settings

logger = logging.getLogger(__name__)


def send_cuadratura(
    recipients: list[str],
    periodo: str,
    attachment: Path,
    n_differences: int,
    n_total: int,
) -> None:
    """Sends the reconciliation Excel to the given recipients via SMTP."""
    if not recipients:
        logger.info("Sin destinatarios — correo no enviado")
        return

    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("Credenciales SMTP no configuradas — correo no enviado")
        return

    diff_word = "diferencia" if n_differences == 1 else "diferencias"
    subject   = f"Cuadratura Remuneraciones — Período {periodo}"
    body      = (
        f"Estimado/a,\n\n"
        f"Se adjunta el archivo de cuadratura para el período {periodo}.\n\n"
        f"Resumen:\n"
        f"  • Total registros analizados : {n_total}\n"
        f"  • Registros con {diff_word}    : {n_differences}\n\n"
        f"Las filas marcadas en rojo presentan diferencias entre Oracle y Buk.\n\n"
        f"Saludos,\n"
        f"Proceso Automático de Cuadratura"
    )

    msg            = MIMEMultipart()
    msg["From"]    = settings.smtp_from or settings.smtp_user
    msg["To"]      = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with attachment.open("rb") as fh:
        part = MIMEApplication(fh.read(), Name=attachment.name)
    part["Content-Disposition"] = f'attachment; filename="{attachment.name}"'
    msg.attach(part)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.sendmail(
            settings.smtp_from or settings.smtp_user,
            recipients,
            msg.as_bytes(),
        )

    logger.info("Correo enviado a: %s", ", ".join(recipients))
