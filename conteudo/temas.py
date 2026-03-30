"""
Definição de temas e signos por personagem.
"""

import random
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# ── Signos fixos ─────────────────────────────────────────────────────────────

SIGNOS_FIXOS = [
    "Áries", "Touro", "Gêmeos", "Câncer", "Leão", "Virgem",
    "Libra", "Escorpião", "Sagitário", "Capricórnio", "Aquário", "Peixes",
]

# ── Temas disponíveis por personagem ─────────────────────────────────────────

TEMAS_POR_PERSONAGEM = {
    "AnaCartomante": {
        "sorte":     "como atrair sorte e boas energias no dia a dia",
        "amor":      "encontrar ou fortalecer o amor verdadeiro",
        "dinheiro":  "atrair prosperidade e abundância financeira",
        "signos":    "as características e poderes únicos do signo",
        "aleatorio": None,   # escolhido dinamicamente a cada vídeo
    },
}

TEMAS_FIXOS = {
    personagem: [t for t in temas if t != "aleatorio"]
    for personagem, temas in TEMAS_POR_PERSONAGEM.items()
}


# ── Resolvers ─────────────────────────────────────────────────────────────────

def resolver_signo(signo_escolhido: str) -> str:
    """
    Resolve o signo final.
    Se for 'aleatorio', sorteia um da lista de signos fixos.

    Returns:
        Nome do signo final (ex: "Gêmeos")
    """
    if signo_escolhido == "aleatorio":
        signo = random.choice(SIGNOS_FIXOS)
        print(f"  🎲 Signo aleatório sorteado: {signo}")
        return signo
    return signo_escolhido


def resolver_tema(personagem: str, tema_escolhido: str) -> tuple[str, str]:
    """
    Resolve o tema final e a mensagem central.
    Se for 'aleatorio', sorteia um dos temas fixos do personagem.

    Returns:
        (tema_final, mensagem_central)
    """
    temas = TEMAS_POR_PERSONAGEM.get(personagem, {})

    if tema_escolhido == "aleatorio":
        tema_final = random.choice(TEMAS_FIXOS[personagem])
        print(f"  🎲 Tema aleatório sorteado: {tema_final}")
    else:
        tema_final = tema_escolhido

    mensagem = temas.get(tema_final, f"mensagem poderosa e positiva sobre {tema_final}")
    return tema_final, mensagem


def signo_e_relevante(tema_final: str) -> bool:
    """
    Retorna True se o tema exige um signo específico.
    Apenas o tema 'signos' usa o signo diretamente na mensagem.
    Para outros temas, o signo é apenas contexto secundário.
    """
    return tema_final == "signos"


def temas_disponiveis(personagem: str) -> list[str]:
    """Retorna lista de temas disponíveis para o personagem (incluindo 'aleatorio')."""
    return list(TEMAS_POR_PERSONAGEM.get(personagem, {}).keys())