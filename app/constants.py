"""
Constantes e listas padrão do Orchestra Portal
"""

# Lista padrão de instrumentos para autocomplete / select
INSTRUMENTOS_PADRAO = [
    # Cordas
    "Violino",
    "Violino 1",
    "Violino 2",
    "Viola",
    "Violoncelo",
    "Cello",
    "Contrabaixo",
    "Contrabaixo Acústico",
    # Madeiras
    "Flauta",
    "Flauta Transversal",
    "Flauta Piccolo",
    "Oboé",
    "Clarinete",
    "Clarinete Sib",
    "Clarinete Mi",
    "Fagote",
    "Saxofone Soprano",
    "Saxofone Alto",
    "Saxofone Tenor",
    "Saxofone Barítono",
    "Saxofone Baixo",
    # Metais
    "Trompa",
    "Trompete",
    "Trombone",
    "Tuba",
    # Percussão
    "Timpani",
    "Bateria",
    "Vibrafone",
    "Xilofone",
    "Marimba",
    "Glockenspiel",
    # Teclado / outros
    "Piano",
    "Órgão",
    "Harpa",
    "Violão",
    # Voz
    "Voz",
    "Voz Solista",
    "Soprano",
    "Alto",
    "Tenor",
    "Baixo",
]

# Tipos de STAB (Soprano, Alto, Tenor, Baixo) para partes corais
STAB_TIPOS = {
    "soprano": "Soprano",
    "alto": "Alto",
    "tenor": "Tenor",
    "baixo": "Baixo",
    "completo": "Partitura Completa (STAB)",
}

# Extensões de arquivo permitidas para upload
ALLOWED_EXTENSIONS = {".pdf", ".xml", ".mxl", ".mus", ".sib", ".musicxml"}

# Tamanho máximo de arquivo em MB
MAX_FILE_SIZE_MB = 50

# Caminho relativo para uploads temporários
TEMP_UPLOAD_DIR = "uploads/temp"

# Caminho relativo para uploads permanentes
PERMANENT_UPLOAD_DIR = "uploads/obras"
