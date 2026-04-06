# automation_flow/flows/anuncios/modelos/ana_indica.py
from pathlib import Path
from automation_flow.core.config import settings

# ---------------------------------------------------------------------------
# IDENTIDADE
# ---------------------------------------------------------------------------
NOME = "AnaIndica"
SLUG = "ana_indica"

# ---------------------------------------------------------------------------
# DESCRIÇÃO VISUAL (usada no prompt do Gemini para geração de imagem)
# ---------------------------------------------------------------------------
DESCRICAO_MODELO = (
    "Brazilian woman, approximately 28 years old, light brown skin, "
    "long dark wavy hair, natural makeup, friendly and confident expression, "
    "casual-chic style"
)

# ---------------------------------------------------------------------------
# VARIANTES DE MÃO para filmagens POV
# ---------------------------------------------------------------------------
MAOS = {
    "clara": "fair skin hands, perfectly shaped nails painted red",
    "morena": "brown skin hands, perfectly shaped nails painted blue",
}

MAO_PADRAO = "clara"

# ---------------------------------------------------------------------------
# VOZ / PERSONA DE TEXTO para os diálogos dos vídeos
# ---------------------------------------------------------------------------
VOZ = (
    "AnaIndica é uma influencer brasileira de moda e lifestyle, fala de forma "
    "descontraída e empolgada, usa gírias modernas do TikTok, faz recomendações "
    "como uma amiga que achou algo incrível e precisa contar pra você agora. "
    "Tom: animado, próximo, informal. Nunca usa palavras difíceis."
)

# ---------------------------------------------------------------------------
# CONFIGURAÇÕES POR TIPO DE FILMAGEM
# (cenário padrão injetado no prompt do Gemini e do Flow/Veo3)
# ---------------------------------------------------------------------------
CONFIGS_FILMAGEM = {
    "POV-Maos": {
        "mao": MAO_PADRAO,
        "cenario": (
            "white linen bed sheet background, soft diffused natural light "
            "from a window on the left, cozy and aesthetic feel"
        ),
        "angulo_camera": "top-down overhead view, hands centered in frame",
        "cenas_padrao": 3,
    },
    "ModeloFrontal": {
        "cenario": (
            "minimalist white room, soft ring light, shot on smartphone, "
            "slightly blurred background"
        ),
        "angulo_camera": "front-facing selfie angle, eye level, vertical 9:16",
        "cenas_padrao": 3,
    },
    "ModeloPes": {
        "cenario": (
            "light wooden floor, natural light, clean background"
        ),
        "angulo_camera": "low angle looking down at feet, vertical frame",
        "cenas_padrao": 3,
    },
    "ModeloCaminhando": {
        "cenario": (
            "urban street or shopping mall, natural light, candid aesthetic"
        ),
        "angulo_camera": "follows the model walking, slightly behind or side angle",
        "cenas_padrao": 3,
    },
    "ProdutoFlat": {
        "cenario": (
            "white marble surface, aesthetic props (flowers, ribbons), "
            "soft studio light"
        ),
        "angulo_camera": "overhead flat lay, perfectly centered",
        "cenas_padrao": 3,
    },
}

# ---------------------------------------------------------------------------
# DIRETÓRIO BASE NO GOOGLE DRIVE
# ---------------------------------------------------------------------------
DIR_BASE = Path(getattr(settings, "PRODUTOS_DIR", r"G:\Meu Drive\Produtos")) / "AnaIndica"


class AnaIndica:
    NOME = NOME
    SLUG = SLUG
    DESCRICAO_MODELO = DESCRICAO_MODELO
    MAOS = MAOS
    MAO_PADRAO = MAO_PADRAO
    VOZ = VOZ
    CONFIGS_FILMAGEM = CONFIGS_FILMAGEM
    DIR_BASE = DIR_BASE

    @classmethod
    def tipos_filmagem(cls) -> list[str]:
        return list(cls.CONFIGS_FILMAGEM.keys())

    @classmethod
    def config_filmagem(cls, tipo: str) -> dict:
        if tipo not in cls.CONFIGS_FILMAGEM:
            raise ValueError(
                f"Tipo de filmagem {tipo!r} não configurado para {cls.NOME}. "
                f"Disponíveis: {list(cls.CONFIGS_FILMAGEM.keys())}"
            )
        return cls.CONFIGS_FILMAGEM[tipo]

    @classmethod
    def dir_tipo(cls, tipo: str) -> Path:
        return cls.DIR_BASE / tipo