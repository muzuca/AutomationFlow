# automation_flow/flows/anuncios/modelos/lara_select.py
from pathlib import Path
from automation_flow.core.config import settings

# ---------------------------------------------------------------------------
# IDENTIDADE
# ---------------------------------------------------------------------------
NOME = "LaraSelect"
SLUG = "lara_select"

# ---------------------------------------------------------------------------
# DESCRIÇÃO VISUAL
# ---------------------------------------------------------------------------
DESCRICAO_MODELO = (
    "Brazilian woman, approximately 30 years old, dark brown skin, "
    "short natural curly hair, bold makeup with emphasis on the eyes, "
    "sophisticated and powerful expression, fashion-forward style"
)

# ---------------------------------------------------------------------------
# VARIANTES DE MÃO para filmagens POV
# ---------------------------------------------------------------------------
MAOS = {
    "clara": "fair skin hands, perfectly shaped nails painted red",
    "morena": "brown skin hands, perfectly shaped nails painted blue",
}

MAO_PADRAO = "morena"

# ---------------------------------------------------------------------------
# VOZ / PERSONA DE TEXTO
# ---------------------------------------------------------------------------
VOZ = (
    "LaraSelect é uma influencer brasileira de moda premium e curadoria de produtos, "
    "fala com autoridade e sofisticação, mas ainda de forma acessível. "
    "Apresenta produtos como escolhas exclusivas e certeiras. "
    "Tom: confiante, elegante, aspiracional. Usa vocabulário atual mas nunca vulgar."
)

# ---------------------------------------------------------------------------
# CONFIGURAÇÕES POR TIPO DE FILMAGEM
# ---------------------------------------------------------------------------
CONFIGS_FILMAGEM = {
    "POV-Maos": {
        "mao": MAO_PADRAO,
        "cenario": (
            "dark velvet surface, dramatic side lighting, luxury editorial feel"
        ),
        "angulo_camera": "top-down overhead view, hands centered in frame",
        "cenas_padrao": 3,
    },
    "ModeloFrontal": {
        "cenario": (
            "sleek dark studio background, professional lighting setup, "
            "editorial fashion vibe"
        ),
        "angulo_camera": "front-facing angle, slightly below eye level, vertical 9:16",
        "cenas_padrao": 3,
    },
    "ModeloPes": {
        "cenario": (
            "glossy black floor, dramatic studio light, high-fashion editorial"
        ),
        "angulo_camera": "low angle looking down at feet, vertical frame",
        "cenas_padrao": 3,
    },
    "ModeloCaminhando": {
        "cenario": (
            "luxury hotel lobby or upscale shopping district, "
            "warm golden light, aspirational setting"
        ),
        "angulo_camera": "follows the model walking, cinematic tracking shot",
        "cenas_padrao": 3,
    },
    "ProdutoFlat": {
        "cenario": (
            "black marble surface, gold accent props, dramatic directional light"
        ),
        "angulo_camera": "overhead flat lay, perfectly centered, editorial composition",
        "cenas_padrao": 3,
    },
}

# ---------------------------------------------------------------------------
# DIRETÓRIO BASE NO GOOGLE DRIVE
# ---------------------------------------------------------------------------
DIR_BASE = Path(getattr(settings, "PRODUTOS_DIR", r"G:\Meu Drive\Produtos")) / "LaraSelect"


class LaraSelect:
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