import html
import re
import unicodedata
from datetime import datetime, timezone

_BLOCO = re.compile(r"</?(p|div|br|li|ul|ol|h[1-6]|tr)[^>]*>", re.I)
_TAG = re.compile(r"<[^>]+>")


def limpar_html(texto: str | None) -> str:
    """Converte HTML em texto simples, preservando quebras de linha entre blocos."""
    if not texto:
        return ""
    texto = _BLOCO.sub("\n", texto)
    texto = _TAG.sub("", texto)
    texto = html.unescape(texto)
    texto = re.sub(r"[ \t\xa0]+", " ", texto)
    texto = re.sub(r"\n\s*\n+", "\n", texto)
    return texto.strip()


def normalizar(texto: str | None) -> str:
    """Minúsculas e sem acentos, para comparar 'Segurança' com 'seguranca'."""
    texto = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in texto if not unicodedata.combining(c)).lower()


def parse_data(valor) -> datetime | None:
    """Aceita ISO 8601 ou timestamp (segundos ou milissegundos). Sempre devolve UTC-aware."""
    if valor in (None, ""):
        return None
    try:
        if isinstance(valor, (int, float)):
            seg = valor / 1000 if valor > 1e11 else valor
            return datetime.fromtimestamp(seg, tz=timezone.utc)
        dt = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, OSError, OverflowError):
        return None
