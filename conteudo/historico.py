"""
Histórico de roteiros gerados — evita repetição de conteúdo.
Persiste em JSON na raiz do projeto.
"""

import json
import time
from pathlib import Path
from difflib import SequenceMatcher

PROJECT_ROOT  = Path(__file__).resolve().parent.parent
HISTORICO_PATH = PROJECT_ROOT / "historico_roteiros.json"

# Similaridade máxima permitida (0.0 = totalmente diferente, 1.0 = idêntico)
LIMIAR_SIMILARIDADE = 0.75

# Quantos roteiros recentes comparar
JANELA_COMPARACAO = 20


def _carregar() -> list[dict]:
    if not HISTORICO_PATH.exists():
        return []
    try:
        with open(HISTORICO_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _salvar(historico: list[dict]):
    with open(HISTORICO_PATH, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)


def _similaridade(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _roteiro_para_texto(roteiro: dict) -> str:
    """Converte o roteiro em string para comparação."""
    dialogos = " ".join(roteiro.get("dialogos", []))
    descricao = roteiro.get("descricao", "")
    return f"{descricao} {dialogos}"


def registrar_roteiro(personagem: str, signo: str, tema: str, roteiro: dict):
    """Salva o roteiro no histórico."""
    historico = _carregar()
    historico.append({
        "timestamp":  time.strftime("%Y-%m-%d %H:%M:%S"),
        "personagem": personagem,
        "signo":      signo,
        "tema":       tema,
        "descricao":  roteiro.get("descricao", ""),
        "dialogos":   roteiro.get("dialogos", []),
        "hashtags":   roteiro.get("hashtags", []),
    })
    _salvar(historico)


def roteiro_e_repetido(personagem: str, tema: str, roteiro: dict) -> bool:
    """
    Verifica se o roteiro é muito similar a algum recente do mesmo personagem/tema.
    Retorna True se for repetido (deve gerar novamente).
    """
    historico = _carregar()

    # Filtra apenas os recentes do mesmo personagem e tema
    recentes = [
        h for h in historico
        if h["personagem"] == personagem and h["tema"] == tema
    ][-JANELA_COMPARACAO:]

    if not recentes:
        return False

    texto_novo = _roteiro_para_texto(roteiro)

    for anterior in recentes:
        texto_anterior = _roteiro_para_texto(anterior)
        sim = _similaridade(texto_novo, texto_anterior)
        if sim >= LIMIAR_SIMILARIDADE:
            print(f"  ⚠ Roteiro muito similar a um anterior (similaridade: {sim:.0%}). "
                  f"Gerando novamente...")
            return True

    return False


def listar_resumo() -> list[dict]:
    """Retorna resumo dos últimos roteiros para exibição."""
    historico = _carregar()
    return [
        {
            "data":       h["timestamp"],
            "personagem": h["personagem"],
            "tema":       h["tema"],
            "descricao":  h["descricao"][:60] + "...",
        }
        for h in historico[-10:]
    ]