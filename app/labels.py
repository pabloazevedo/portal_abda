"""
Portal — Labels centralizadas para Enums de Patrimônio.
Fonte única de verdade para _TIPO_LABEL e _STATUS_LABEL (D-01).
"""

from app.models import TipoItem, StatusPatrimonio

TIPO_LABEL: dict[TipoItem, str] = {
    TipoItem.Instrumento: "Instrumento",
    TipoItem.Movel:       "Móvel",
    TipoItem.Eletronico:  "Eletrônico",
    TipoItem.Partitura:   "Partitura",
    TipoItem.Decoracao:   "Decoração",
    TipoItem.Outros:      "Outros",
}

STATUS_LABEL: dict[StatusPatrimonio, str] = {
    StatusPatrimonio.Disponivel: "Disponível",
    StatusPatrimonio.Emprestado: "Emprestado",
    StatusPatrimonio.Manutencao: "Manutenção",
    StatusPatrimonio.Baixa:      "Baixa",
}
