"""Decide se uma vaga interessa e anota alertas sobre o que não está claro."""
import re
from datetime import datetime, timezone

from .modelo import Vaga
from .util import normalizar

RE_ESTAGIO = re.compile(r"estagi|\bintern\b|\binterns\b|internship|\bco-?op\b")

# Locais que indicam que alguém no Brasil pode se candidatar
RE_BRASIL_OK = re.compile(
    r"\b(brazil|brasil|latam|latin america|america latina|south america|americas|"
    r"worldwide|anywhere|global|world|international)\b")

RE_SO_REMOTO = re.compile(r"\b(remote|remoto|fully|100%?)\b|[-,/()|]")

RE_AUTORIZACAO = re.compile(
    r"(authoriz\w*|eligible|right) to work in (the )?(us|u\.s\.?|united states|usa|uk|canada|eu|europe)"
    r"|must (be )?(reside|live|located|based) in"
    r"|visa sponsorship|security clearance")

RE_PERIODO = re.compile(r"(\d{1,2})\s*(o|º|°|ª)?\s*(periodo|semestre|ano)")

RE_SECAO_REQ = re.compile(
    r"requisitos|requirements|qualifica|o que (voce precisa|esperamos|buscamos)"
    r"|what (you|we)('ll)? (need|bring|look)|who you are|you have|voce tem|minimum|must have")


def extrair_requisitos(texto: str, maximo: int = 450) -> str:
    linhas = [l.strip() for l in texto.split("\n")]
    for i, linha in enumerate(linhas):
        n = normalizar(linha)
        if len(n) < 120 and RE_SECAO_REQ.search(n):
            itens = [l for l in linhas[i + 1:i + 10] if l]
            trecho = " • ".join(itens)
            if trecho:
                return trecho[:maximo] + ("…" if len(trecho) > maximo else "")
    return ""


def _padrao(palavra: str) -> re.Pattern:
    p = re.escape(normalizar(palavra))
    # palavras curtas (ti, ia, ai, soc) exigem palavra inteira para evitar falso positivo
    return re.compile(rf"\b{p}\b" if len(palavra) <= 3 else rf"\b{p}")


class Filtro:
    def __init__(self, cfg: dict):
        area = cfg["area"]
        self.titulo = [_padrao(p) for p in area["palavras_titulo"]]
        self.descricao = [_padrao(p) for p in area.get("palavras_descricao", [])]
        self.excluir = [_padrao(p) for p in cfg.get("excluir_titulo", [])]
        local = cfg["local"]
        self.cidades = [normalizar(c) for c in local["cidades_hibrido_presencial"]]
        self.incluir_presencial = local.get("incluir_presencial", False)
        self.aceitar_incertas = local.get("incluir_remotas_sem_pais_claro", True)

    @staticmethod
    def _tem(texto: str, padroes) -> bool:
        return any(p.search(texto) for p in padroes)

    def _na_cidade(self, v: Vaga) -> bool:
        loc = normalizar(v.local)
        return any(c in loc for c in self.cidades)

    def avaliar(self, v: Vaga, agora: datetime | None = None) -> bool:
        agora = agora or datetime.now(timezone.utc)
        titulo, desc, tipo = normalizar(v.cargo), normalizar(v.descricao), normalizar(v.tipo)

        # 1. É estágio?
        if self._tem(titulo, self.excluir):
            return False
        if not (RE_ESTAGIO.search(titulo) or "intern" in tipo):
            return False

        # 2. É da área?
        if not (self._tem(titulo, self.titulo) or self._tem(desc, self.descricao)):
            return False

        # 3. Inscrições abertas? (APIs só listam vagas ativas; aqui checamos o prazo quando existe)
        if v.prazo and v.prazo < agora:
            return False

        # 4. Modalidade e local
        if v.modalidade == "Remoto":
            if not self._remota_ok(v, desc):
                return False
        elif v.modalidade == "Híbrido":
            if not self._na_cidade(v):
                return False
        elif v.modalidade == "Presencial":
            if not (self.incluir_presencial and self._na_cidade(v)):
                return False
        else:  # Não informado
            if not self._na_cidade(v):
                return False
            v.alertas.append("Modalidade não informada na vaga.")

        # 5. Requisitos e alertas extras
        v.requisitos = extrair_requisitos(v.descricao)
        if not v.requisitos:
            v.alertas.append("Requisitos não identificados automaticamente: confira no link.")
        m = RE_PERIODO.search(desc)
        if m:
            v.alertas.append(f"Menciona período/semestre ('{m.group(0)}'): confira se o 3º período atende.")
        if not v.oficial:
            v.alertas.append(f"Link de agregador ({v.fonte}): confirme vaga e inscrições na página oficial da empresa.")
        return True

    def _remota_ok(self, v: Vaga, desc: str) -> bool:
        if v.aceita_brasil is None:
            loc = normalizar(v.local)
            if RE_BRASIL_OK.search(loc):
                pass
            elif not RE_SO_REMOTO.sub(" ", loc).strip():
                if not self.aceitar_incertas:
                    return False
                v.alertas.append("Local não especificado: confirme se aceita candidatos no Brasil.")
            else:
                return False  # restrita a outro país/região (ex.: "US only")
        if RE_AUTORIZACAO.search(desc):
            v.alertas.append("Descrição menciona autorização de trabalho, visto ou residência em outro país.")
        return True
