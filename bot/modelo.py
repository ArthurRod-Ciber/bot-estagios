from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Vaga:
    uid: str                      # id único e estável (fonte:empresa:id)
    fonte: str                    # Gupy, Greenhouse, Lever, Remotive
    empresa: str
    cargo: str
    url: str
    modalidade: str               # Remoto | Híbrido | Presencial | Não informado
    local: str = ""
    descricao: str = ""
    publicado: datetime | None = None
    prazo: datetime | None = None
    tipo: str = ""                # dica de tipo de contrato vinda da fonte
    oficial: bool = True          # False = agregador (confirmar na página da empresa)
    aceita_brasil: bool | None = None  # None = o filtro decide pelo texto de local
    requisitos: str = ""
    alertas: list[str] = field(default_factory=list)
