"""Coletores de vagas. Cada função recebe a config da fonte e devolve list[Vaga].

Todas usam endpoints públicos (sem login). Erros de uma empresa/termo não derrubam o resto.
"""
import html as _html
import json
import logging
import re
import time

import requests

from .modelo import Vaga
from .util import limpar_html, normalizar, parse_data

log = logging.getLogger(__name__)

HEADERS = {"User-Agent": "vagas-estagio-bot/1.0 (projeto pessoal de estudante)"}
TIMEOUT = 20


def _get(url, params=None):
    r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def _modalidade_por_texto(texto: str) -> str:
    t = normalizar(texto)
    if re.search(r"remot|remote|home ?office|anywhere", t):
        return "Remoto"
    if re.search(r"hibrid|hybrid", t):
        return "Híbrido"
    return "Presencial" if t.strip() else "Não informado"


# ---------------------------------------------------------------- Gupy (Brasil)
_GUPY_MOD = {"remote": "Remoto", "hybrid": "Híbrido", "on-site": "Presencial", "onsite": "Presencial"}

# Endpoint público que o próprio portal.gupy.io usa (o antigo portal.api.gupy.io foi desativado).
_GUPY_URL = "https://employability-portal.gupy.io/api/v1/jobs"
_TENTATIVAS = 3


def _gupy_pagina(termo: str, limite: int, offset: int) -> list[dict]:
    """Busca uma página, repetindo em bloqueios temporários da borda (403/404/429/5xx)."""
    for tentativa in range(1, _TENTATIVAS + 1):
        r = requests.get(_GUPY_URL, params={"jobName": termo, "limit": limite, "offset": offset},
                         headers=HEADERS, timeout=TIMEOUT)
        if r.ok:
            dados = r.json()
            if isinstance(dados, list):
                return dados
            return dados.get("data") or dados.get("jobs") or dados.get("results") or []
        if r.status_code in (403, 404, 429) or r.status_code >= 500:
            log.info("Gupy '%s': HTTP %s (tentativa %d/%d) %s", termo, r.status_code,
                     tentativa, _TENTATIVAS, r.text[:120].replace("\n", " "))
            time.sleep(2 * tentativa)
            continue
        r.raise_for_status()
    raise requests.HTTPError(f"HTTP {r.status_code} após {_TENTATIVAS} tentativas: {r.url}")


def buscar_gupy(cfg) -> list[Vaga]:
    vagas: dict[str, Vaga] = {}
    limite = cfg.get("limite", 10)
    paginas = cfg.get("max_paginas", 5)
    falhas = 0
    for termo in cfg.get("termos", []):
        if falhas >= 2 and not vagas:
            log.warning("Gupy parece indisponível ou bloqueando este servidor; pulando os demais termos.")
            break
        for pagina in range(paginas):
            try:
                itens = _gupy_pagina(termo, limite, pagina * limite)
            except requests.RequestException as e:
                log.warning("Gupy '%s' falhou: %s", termo, e)
                falhas += 1
                break
            for j in itens:
                uid = f"gupy:{j.get('id')}"
                if uid in vagas:
                    continue
                mod = _GUPY_MOD.get(j.get("workplaceType") or "") or (
                    "Remoto" if j.get("isRemoteWork") else "Não informado")
                local = ", ".join(x for x in (j.get("city"), j.get("state"), j.get("country")) if x)
                vagas[uid] = Vaga(
                    uid=uid, fonte="Gupy",
                    empresa=j.get("careerPageName") or j.get("company") or "?",
                    cargo=j.get("name") or j.get("title") or "",
                    url=j.get("jobUrl") or j.get("applyUrl") or "",
                    modalidade=mod, local=local,
                    descricao=limpar_html(j.get("description")),
                    publicado=parse_data(j.get("publishedDate")),
                    prazo=parse_data(j.get("applicationDeadline")),
                    tipo=j.get("type") or j.get("employmentType") or "",
                    aceita_brasil=True,  # Gupy é plataforma brasileira
                )
            if len(itens) < limite:   # última página
                break
    return list(vagas.values())


_RE_NEXT = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)
_RE_SCRIPT_STYLE = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
_GUPY_CHAVES = ("description", "responsibilities", "prerequisites", "additionalInformation")


def _procurar_textos(obj, chaves) -> dict[str, str]:
    """Procura, em qualquer nível do JSON, o primeiro texto de cada chave pedida."""
    achados, pilha = {}, [obj]
    while pilha:
        o = pilha.pop()
        if isinstance(o, dict):
            for k, val in o.items():
                if k in chaves and isinstance(val, str) and val.strip() and k not in achados:
                    achados[k] = val
                elif isinstance(val, (dict, list)):
                    pilha.append(val)
        elif isinstance(o, list):
            pilha.extend(o)
    return achados


def _itens(texto_html: str, maximo: int = 450) -> str:
    linhas = [l.strip(" -•*·\t") for l in limpar_html(texto_html).split("\n")]
    trecho = " • ".join(l for l in linhas if l)
    return trecho[:maximo] + ("…" if len(trecho) > maximo else "")


def detalhar_gupy(v: Vaga, html_pagina: str | None = None) -> None:
    """Abre a página da vaga e completa descrição e requisitos (a listagem só traz um resumo)."""
    if html_pagina is None:
        r = requests.get(v.url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        html_pagina = r.text

    m = _RE_NEXT.search(html_pagina)
    if m:
        try:
            dados = _procurar_textos(json.loads(m.group(1)), _GUPY_CHAVES)
        except json.JSONDecodeError:
            dados = {}
        if dados:
            v.descricao = "\n".join(limpar_html(dados[k]) for k in _GUPY_CHAVES if k in dados)
            if dados.get("prerequisites"):
                v.requisitos = _itens(dados["prerequisites"])
            return
    # Plano B: texto da página inteira (sem scripts), e o filtro tenta achar a seção de requisitos
    v.descricao = limpar_html(_RE_SCRIPT_STYLE.sub("", html_pagina))


# ---------------------------------------------------------------- Greenhouse
def buscar_greenhouse(cfg) -> list[Vaga]:
    vagas = []
    for board in cfg.get("empresas", []):
        try:
            dados = _get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
                         {"content": "true"})
        except requests.RequestException as e:
            log.warning("Greenhouse '%s' falhou: %s", board, e)
            continue
        for j in dados.get("jobs", []):
            local = (j.get("location") or {}).get("name", "")
            vagas.append(Vaga(
                uid=f"greenhouse:{board}:{j.get('id')}", fonte="Greenhouse",
                empresa=j.get("company_name") or board.title(),
                cargo=j.get("title") or "",
                url=j.get("absolute_url") or "",
                modalidade=_modalidade_por_texto(local), local=local,
                # o 'content' do Greenhouse vem com HTML escapado duas vezes
                descricao=limpar_html(_html.unescape(j.get("content") or "")),
                publicado=parse_data(j.get("first_published") or j.get("updated_at")),
            ))
    return vagas


# ---------------------------------------------------------------- Lever
_LEVER_MOD = {"remote": "Remoto", "hybrid": "Híbrido", "onsite": "Presencial"}


def buscar_lever(cfg) -> list[Vaga]:
    vagas = []
    for emp in cfg.get("empresas", []):
        try:
            dados = _get(f"https://api.lever.co/v0/postings/{emp}", {"mode": "json"})
        except requests.RequestException as e:
            log.warning("Lever '%s' falhou: %s", emp, e)
            continue
        for j in dados:
            cat = j.get("categories") or {}
            local = cat.get("location") or ", ".join(cat.get("allLocations") or [])
            partes = [j.get("descriptionPlain") or ""]
            for lista in j.get("lists") or []:
                partes += [lista.get("text") or "", limpar_html(lista.get("content"))]
            vagas.append(Vaga(
                uid=f"lever:{emp}:{j.get('id')}", fonte="Lever",
                empresa=emp.replace("-", " ").title(),
                cargo=j.get("text") or "",
                url=j.get("hostedUrl") or "",
                modalidade=_LEVER_MOD.get(j.get("workplaceType") or "") or _modalidade_por_texto(local),
                local=local,
                descricao="\n".join(p for p in partes if p),
                publicado=parse_data(j.get("createdAt")),
                tipo=cat.get("commitment") or "",
            ))
    return vagas


# ---------------------------------------------------------------- Remotive (agregador remoto)
def buscar_remotive(cfg) -> list[Vaga]:
    vagas: dict[str, Vaga] = {}
    for termo in cfg.get("termos", []):
        try:
            dados = _get("https://remotive.com/api/remote-jobs", {"search": termo})
        except requests.RequestException as e:
            log.warning("Remotive '%s' falhou: %s", termo, e)
            continue
        for j in dados.get("jobs", []):
            uid = f"remotive:{j.get('id')}"
            vagas.setdefault(uid, Vaga(
                uid=uid, fonte="Remotive",
                empresa=j.get("company_name") or "?",
                cargo=j.get("title") or "",
                url=j.get("url") or "",
                modalidade="Remoto",
                local=j.get("candidate_required_location") or "",
                descricao=limpar_html(j.get("description")),
                publicado=parse_data(j.get("publication_date")),
                tipo=j.get("job_type") or "",
                oficial=False,
            ))
    return list(vagas.values())


# Fontes cuja listagem vem resumida e que sabemos detalhar
DETALHAR = {"Gupy": detalhar_gupy}

FONTES = {
    "gupy": buscar_gupy,
    "greenhouse": buscar_greenhouse,
    "lever": buscar_lever,
    "remotive": buscar_remotive,
}
