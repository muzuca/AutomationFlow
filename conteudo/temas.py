"""
Definição de temas, signos e regras por personagem.
Estrutura desacoplada para facilitar inclusão de novos personagens.
"""

import random
from pathlib import Path
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


# ── Signos fixos globais ─────────────────────────────────────────────────────


SIGNOS_FIXOS = [
    "Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem",
    "Libra", "Escorpião", "Sagitário", "Capricórnio", "Aquário", "Peixes",
]


# ── Catálogo de personagens ──────────────────────────────────────────────────
# Cada personagem define:
# - usa_signos: se o fluxo desse personagem depende de signo
# - signos_disponiveis: lista de signos válidos (ou [])
# - temas: dict tema -> mensagem central base
# - fallback_mensagem: função ou texto-base para temas novos/futuros


PERSONAGENS_CONFIG = {
    "AnaCartomante": {
        "usa_signos": True,
        "signos_disponiveis": SIGNOS_FIXOS,
        "temas": {
            "sorte": "como atrair sorte e boas energias no dia a dia",
            "amor": "encontrar ou fortalecer o amor verdadeiro",
            "dinheiro": "atrair prosperidade e abundância financeira",
            "signos": "as características e poderes únicos do signo",
            "aleatorio": None,
        },
        "fallback_mensagem": lambda tema: f"mensagem poderosa e positiva sobre {tema}",
    },
    "CoachEspiritual": {
        "usa_signos": False,
        "signos_disponiveis": [],
        "temas": {
            "superacao": "superar a dor com fé, coragem e presença de Deus",
            "amor": "curar o coração e aprender a amar com paz e propósito",
            "fe": "fortalecer a fé mesmo em dias difíceis e silenciosos",
            "deus": "confiar em Deus e descansar no tempo dEle",
            "salmos": "buscar força, consolo e direção espiritual através dos salmos",
            "aleatorio": None,
        },
        "fallback_mensagem": lambda tema: f"mensagem espiritual, acolhedora e poderosa sobre {tema}",
    },
}


TEMAS_FIXOS = {
    personagem: [tema for tema in config["temas"].keys() if tema != "aleatorio"]
    for personagem, config in PERSONAGENS_CONFIG.items()
}


# ── Helpers genéricos ────────────────────────────────────────────────────────


def personagem_existe(personagem: str) -> bool:
    return personagem in PERSONAGENS_CONFIG


def obter_config_personagem(personagem: str) -> dict:
    if personagem not in PERSONAGENS_CONFIG:
        raise ValueError(f"Personagem desconhecido: {personagem}")
    return PERSONAGENS_CONFIG[personagem]


# ── Resolvers ────────────────────────────────────────────────────────────────


def resolver_signo(personagem: str, signo_escolhido: str | None = None) -> str | None:
    """
    Resolve o signo final para o personagem.
    - Se o personagem não usa signos, retorna None.
    - Se signo_escolhido for 'aleatorio', sorteia um signo válido.
    - Se não vier signo, sorteia automaticamente quando o personagem usa signos.
    """
    config = obter_config_personagem(personagem)

    if not config["usa_signos"]:
        return None

    signos_disponiveis = config["signos_disponiveis"]

    if not signo_escolhido or signo_escolhido == "aleatorio":
        signo = random.choice(signos_disponiveis)
        print(f"  🎲 Signo aleatório sorteado: {signo}")
        return signo

    if signo_escolhido not in signos_disponiveis:
        raise ValueError(f"Signo inválido para {personagem}: {signo_escolhido}")

    return signo_escolhido


def resolver_tema(personagem: str, tema_escolhido: str) -> tuple[str, str]:
    """
    Resolve o tema final e a mensagem central.
    Se for 'aleatorio', sorteia um dos temas fixos do personagem.

    Returns:
        (tema_final, mensagem_central)
    """
    config = obter_config_personagem(personagem)
    temas = config["temas"]

    if tema_escolhido == "aleatorio":
        tema_final = random.choice(TEMAS_FIXOS[personagem])
        print(f"  🎲 Tema aleatório sorteado: {tema_final}")
    else:
        tema_final = tema_escolhido

    fallback = config["fallback_mensagem"]
    mensagem = temas.get(tema_final)

    if mensagem is None:
        mensagem = fallback(tema_final) if callable(fallback) else str(fallback)

    return tema_final, mensagem


def tema_exige_signo(personagem: str, tema_final: str) -> bool:
    """
    Retorna True se o tema exige uso direto de signo.
    Regra atual:
    - Ana: apenas 'signos'
    - Coach: nenhum tema exige signo
    """
    if personagem == "AnaCartomante":
        return tema_final == "signos"
    return False


def signos_disponiveis(personagem: str) -> list[str]:
    """Retorna os signos disponíveis para o personagem."""
    config = obter_config_personagem(personagem)
    if not config["usa_signos"]:
        return []
    return list(config["signos_disponiveis"])


def temas_disponiveis(personagem: str) -> list[str]:
    """Retorna lista de temas disponíveis para o personagem (incluindo 'aleatorio')."""
    config = obter_config_personagem(personagem)
    return list(config["temas"].keys())


def usa_signos(personagem: str) -> bool:
    """Retorna se o personagem usa signos no fluxo."""
    config = obter_config_personagem(personagem)
    return bool(config["usa_signos"])


def personagens_disponiveis() -> list[str]:
    """Retorna a lista de personagens cadastrados."""
    return list(PERSONAGENS_CONFIG.keys())