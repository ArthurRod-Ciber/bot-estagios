"""Busca vagas de estágio, filtra e envia e-mail só quando há novidades.

Uso:
    python -m bot.main            # busca e envia e-mail
    python -m bot.main --dry-run  # busca e imprime no terminal (não envia nem salva estado)
"""
import argparse
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from . import fontes
from .email_envio import enviar
from .filtro import Filtro

RAIZ = Path(__file__).resolve().parent.parent
ESTADO = RAIZ / "data" / "seen.json"
log = logging.getLogger("bot")


def carregar_estado() -> dict:
    if ESTADO.exists():
        estado = json.loads(ESTADO.read_text(encoding="utf-8"))
    else:
        estado = {}
    estado.setdefault("vistas", {})
    estado.setdefault("ultima_busca", {})
    return estado


def salvar_estado(estado: dict) -> None:
    ESTADO.parent.mkdir(exist_ok=True)
    ESTADO.write_text(json.dumps(estado, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                      encoding="utf-8")


def coletar(cfg: dict, estado: dict, agora: datetime) -> list:
    todas = []
    for nome, fcfg in cfg["fontes"].items():
        if not fcfg.get("ativo", True):
            continue
        intervalo = fcfg.get("intervalo_horas", 0)
        ultima = estado["ultima_busca"].get(nome)
        if intervalo and ultima and agora - datetime.fromisoformat(ultima) < timedelta(hours=intervalo):
            log.info("%s: pulando (intervalo mínimo de %sh).", nome, intervalo)
            continue
        try:
            vagas = fontes.FONTES[nome](fcfg)
        except Exception as e:  # uma fonte quebrada não derruba as outras
            log.error("%s: erro inesperado: %s", nome, e)
            continue
        estado["ultima_busca"][nome] = agora.isoformat(timespec="seconds")
        log.info("%s: %d vaga(s) coletada(s).", nome, len(vagas))
        todas.extend(vagas)
    return todas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config", default=str(RAIZ / "config.yaml"))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    estado = carregar_estado()
    agora = datetime.now(timezone.utc)

    filtro = Filtro(cfg)
    relevantes = [v for v in coletar(cfg, estado, agora) if filtro.avaliar(v, agora)]
    novas = [v for v in relevantes if v.uid not in estado["vistas"]]
    novas.sort(key=lambda v: v.publicado or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    log.info("%d relevante(s), %d nova(s).", len(relevantes), len(novas))

    lote = novas[: cfg.get("max_vagas_por_email", 25)]
    for v in lote:
        detalhar = fontes.DETALHAR.get(v.fonte)
        if detalhar:
            try:
                detalhar(v)
            except Exception as e:  # sem detalhe, a vaga ainda vai, só com menos informação
                log.warning("Não consegui detalhar %s: %s", v.url, e)
        filtro.anotar(v)
    if lote:
        enviar(lote, total=len(novas), dry_run=args.dry_run)
        for v in lote:
            estado["vistas"][v.uid] = agora.isoformat(timespec="seconds")
    else:
        log.info("Nenhuma vaga nova: nenhum e-mail enviado.")

    limite = agora - timedelta(days=cfg.get("esquecer_apos_dias", 180))
    estado["vistas"] = {k: t for k, t in estado["vistas"].items()
                        if datetime.fromisoformat(t) >= limite}
    if not args.dry_run:
        salvar_estado(estado)
    return 0


if __name__ == "__main__":
    sys.exit(main())
