import logging
import os
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from html import escape

from .modelo import Vaga

log = logging.getLogger(__name__)


def _linha_local(v: Vaga) -> str:
    return f"{v.empresa} · {v.modalidade}" + (f" · {v.local}" if v.local else "")


def montar(vagas: list[Vaga], total: int) -> tuple[str, str, str]:
    hoje = datetime.now().strftime("%d/%m %H:%M")
    assunto = f"[Vagas] {len(vagas)} nova(s) vaga(s) de estágio — {hoje}"
    resto = total - len(vagas)
    aviso_resto = f"Mais {resto} vaga(s) virão no próximo envio." if resto > 0 else ""

    texto = [assunto, ""]
    cards = []
    for v in vagas:
        texto += [f"■ {v.cargo}", f"  {_linha_local(v)}",
                  f"  Requisitos: {v.requisitos or 'não identificados'}"]
        texto += [f"  ⚠ {a}" for a in v.alertas]
        texto += [f"  {v.url}", ""]

        alertas = "".join(f"<li>{escape(a)}</li>" for a in v.alertas)
        cards.append(f"""
<div style="border:1px solid #d0d7de;border-radius:10px;padding:14px;margin:14px 0">
  <div style="font-size:16px;font-weight:bold">{escape(v.cargo)}</div>
  <div style="color:#57606a;margin:4px 0 10px">{escape(_linha_local(v))}</div>
  <div><b>Requisitos:</b> {escape(v.requisitos or 'não identificados')}</div>
  {f'<ul style="color:#9a6700;margin:10px 0 0;padding-left:18px">{alertas}</ul>' if alertas else ''}
  <div style="margin-top:12px"><a href="{escape(v.url)}">Ver vaga ({escape(v.fonte)})</a></div>
</div>""")
    if aviso_resto:
        texto.append(aviso_resto)

    corpo_html = f"""<html><body style="font-family:Arial,Helvetica,sans-serif;max-width:640px;margin:auto">
<h2 style="margin-bottom:0">{len(vagas)} nova(s) vaga(s) de estágio</h2>
<p style="color:#57606a;margin-top:4px">{hoje}</p>
{''.join(cards)}
<p style="color:#57606a">{escape(aviso_resto)}</p>
</body></html>"""
    return assunto, "\n".join(texto), corpo_html


def enviar(vagas: list[Vaga], total: int, dry_run: bool = False) -> None:
    assunto, texto, corpo_html = montar(vagas, total)
    if dry_run:
        print(texto)
        return

    usuario = os.environ["SMTP_USER"]
    senha = os.environ["SMTP_PASSWORD"]
    destino = os.environ.get("EMAIL_TO") or usuario
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    porta = int(os.environ.get("SMTP_PORT", "465"))

    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = assunto, usuario, destino
    msg.set_content(texto)
    msg.add_alternative(corpo_html, subtype="html")

    with smtplib.SMTP_SSL(host, porta, context=ssl.create_default_context(), timeout=30) as s:
        s.login(usuario, senha)
        s.send_message(msg)
    log.info("E-mail enviado para %s com %d vaga(s).", destino, len(vagas))
