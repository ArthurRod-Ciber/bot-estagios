from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

from bot.filtro import Filtro, extrair_requisitos
from bot.modelo import Vaga

CFG = yaml.safe_load((Path(__file__).parent.parent / "config.yaml").read_text(encoding="utf-8"))
F = Filtro(CFG)


def vaga(**kw):
    base = dict(uid="x", fonte="Teste", empresa="ACME", cargo="Estágio em Segurança da Informação",
                url="https://exemplo.com", modalidade="Remoto", aceita_brasil=True)
    base.update(kw)
    return Vaga(**base)


def test_estagio_seguranca_remoto_brasil():
    assert F.avaliar(vaga())

def test_nao_estagio():
    assert not F.avaliar(vaga(cargo="Analista de Segurança da Informação"))

def test_seguranca_do_trabalho_excluida():
    assert not F.avaliar(vaga(cargo="Estágio em Segurança do Trabalho"))

def test_palavra_curta_nao_casa_dentro_de_outra():
    assert not F.avaliar(vaga(cargo="Estágio em Marketing Digital"))
    assert F.avaliar(vaga(cargo="Estágio em TI"))

def test_hibrido_so_em_uberlandia():
    assert F.avaliar(vaga(modalidade="Híbrido", local="Uberlândia, MG"))
    assert not F.avaliar(vaga(modalidade="Híbrido", local="São Paulo, SP"))

def test_presencial_desligado_por_padrao():
    assert not F.avaliar(vaga(modalidade="Presencial", local="Uberlandia"))

def test_remota_internacional():
    assert F.avaliar(vaga(cargo="Security Intern", aceita_brasil=None, local="Worldwide"))
    assert F.avaliar(vaga(cargo="Security Intern", aceita_brasil=None, local="LATAM"))
    assert not F.avaliar(vaga(cargo="Security Intern", aceita_brasil=None, local="USA only"))
    v = vaga(cargo="Security Intern", aceita_brasil=None, local="Remote")
    assert F.avaliar(v) and any("Brasil" in a for a in v.alertas)

def test_alerta_autorizacao_de_trabalho():
    v = vaga(cargo="Security Intern", aceita_brasil=None, local="Anywhere",
             descricao="You must be authorized to work in the United States.")
    assert F.avaliar(v) and any("autorização" in a for a in v.alertas)

def test_prazo_encerrado():
    agora = datetime.now(timezone.utc)
    assert not F.avaliar(vaga(prazo=agora - timedelta(days=1)), agora)

def test_extrair_requisitos_e_alerta_periodo():
    desc = "Sobre nós\nSomos legais\nRequisitos\nCursando a partir do 4º período\nNoções de Linux\nInglês"
    assert "Linux" in extrair_requisitos(desc)
    v = vaga(descricao=desc)
    assert F.avaliar(v)
    F.anotar(v)
    assert "Linux" in v.requisitos
    assert any("4º período" in a for a in v.alertas)

def test_periodo_sem_falso_positivo():
    for desc in ("Estágio de 1 ano com possibilidade de efetivação", "Desejável 2 anos de experiência"):
        v = vaga(descricao=desc)
        F.anotar(v)
        assert not any("período" in a for a in v.alertas), desc
    for desc in ("Cursando o 3º semestre", "a partir do 5 periodo", "estar no 2º ano"):
        v = vaga(descricao=desc)
        F.anotar(v)
        assert any("período" in a for a in v.alertas), desc

def test_suporte_so_tecnico():
    assert F.avaliar(vaga(cargo="Estágio em Suporte Técnico"))
    assert not F.avaliar(vaga(cargo="Pessoa Estagiária em Suporte ao Cliente SaaS (Remoto)"))
    assert not F.avaliar(vaga(cargo="Estágio em Suporte Comercial (Vaga Remota - BH e SP)"))
    assert F.avaliar(vaga(cargo="Programa de estágio - TI"))
