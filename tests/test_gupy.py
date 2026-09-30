import json

from bot.fontes import detalhar_gupy
from bot.modelo import Vaga


def _vaga():
    return Vaga(uid="gupy:1", fonte="Gupy", empresa="X", cargo="Estágio TI",
                url="https://x.gupy.io/job/1", modalidade="Remoto")


def test_detalhar_com_next_data():
    dados = {"props": {"pageProps": {"job": {
        "description": "<p>Venha trabalhar conosco</p>",
        "responsibilities": "<ul><li>Monitorar alertas do SOC</li></ul>",
        "prerequisites": "<ul><li>Cursando Cibersegurança</li><li>Noções de redes</li></ul>",
    }}}}
    html = f'<html><script id="__NEXT_DATA__" type="application/json">{json.dumps(dados)}</script></html>'
    v = _vaga()
    detalhar_gupy(v, html)
    assert v.requisitos == "Cursando Cibersegurança • Noções de redes"
    assert "Monitorar alertas" in v.descricao


def test_detalhar_sem_next_data_usa_texto_da_pagina():
    html = "<html><script>var x=1</script><h2>Requisitos</h2><ul><li>Linux</li></ul></html>"
    v = _vaga()
    detalhar_gupy(v, html)
    assert "Linux" in v.descricao and "var x" not in v.descricao
