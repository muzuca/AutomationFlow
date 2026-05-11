# arquivo: content/historico_persona.py
# descricao: Persistencia individual de historico por persona.
# Cada persona tem seu proprio JSON em logs/historico/<PersonaID>.json
# Registra marcadores estruturados (cenario, roupa, clima, etc.) para anti-repeticao.

import json
import time
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORICO_DIR = PROJECT_ROOT / "logs" / "historico"

# Quantos videos recentes considerar para anti-repeticao
JANELA_ANTI_REPETICAO = 30


def _caminho_persona(persona_id: str) -> Path:
    HISTORICO_DIR.mkdir(parents=True, exist_ok=True)
    return HISTORICO_DIR / f"{persona_id}.json"


def carregar_historico(persona_id: str) -> list[dict]:
    """Carrega historico completo de uma persona."""
    caminho = _caminho_persona(persona_id)
    if not caminho.exists():
        return []
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def salvar_historico(persona_id: str, historico: list[dict]):
    """Salva historico completo de uma persona."""
    caminho = _caminho_persona(persona_id)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)


def registrar_video(
    persona_id: str,
    tema: str,
    signo: str,
    marcadores: dict,
    dialogos: list[str],
    descricao: str,
    hashtags: list[str],
):
    """
    Registra um video gerado com seus marcadores.
    marcadores deve conter chaves como:
      cenario, variacao_roupa, clima_visual, tom_emocional,
      tema_central, tipo_gancho, metafora_principal
    """
    historico = carregar_historico(persona_id)

    entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tema": tema,
        "signo": signo,
        "marcadores": marcadores or {},
        "dialogos": dialogos or [],
        "descricao": descricao or "",
        "hashtags": hashtags or [],
    }

    historico.append(entry)
    salvar_historico(persona_id, historico)


def obter_recentes(persona_id: str, n: int = JANELA_ANTI_REPETICAO) -> list[dict]:
    """Retorna os ultimos N registros de uma persona."""
    historico = carregar_historico(persona_id)
    return historico[-n:]


def montar_contexto_anti_repeticao(persona_id: str) -> str:
    """
    Gera bloco de texto para injetar no prompt do Gemini,
    listando cenarios, roupas, temas, metaforas e dialogos
    ja usados nos ultimos 30 videos.
    """
    recentes = obter_recentes(persona_id)
    if not recentes:
        return ""

    # Coletar marcadores unicos
    cenarios = []
    roupas = []
    climas = []
    tons = []
    temas = []
    ganchos = []
    metaforas = []
    dialogos_exemplos = []

    for entry in recentes:
        m = entry.get("marcadores", {})
        if m.get("cenario"):
            cenarios.append(m["cenario"])
        if m.get("variacao_roupa"):
            roupas.append(m["variacao_roupa"])
        if m.get("clima_visual"):
            climas.append(m["clima_visual"])
        if m.get("tom_emocional"):
            tons.append(m["tom_emocional"])
        if m.get("tema_central"):
            temas.append(m["tema_central"])
        if m.get("tipo_gancho"):
            ganchos.append(m["tipo_gancho"])
        if m.get("metafora_principal"):
            metaforas.append(m["metafora_principal"])

        # Pegar 1o dialogo de cada video como exemplo
        dl = entry.get("dialogos", [])
        if dl:
            dialogos_exemplos.append(dl[0][:100])

    blocos = []
    blocos.append("REGRAS DE NAO REPETICAO (OBRIGATORIO):\n")
    blocos.append(
        "Os itens abaixo foram usados nos ultimos videos. "
        "Voce DEVE criar algo COMPLETAMENTE DIFERENTE.\n"
    )

    if cenarios:
        blocos.append("CENARIOS JA USADOS (escolha um local TOTALMENTE diferente):")
        for c in cenarios[-15:]:
            blocos.append(f'  - "{c}"')
        blocos.append("")

    if roupas:
        blocos.append("VARIACOES VISUAIS JA USADAS (mude a roupa/acessorios):")
        for r in roupas[-10:]:
            blocos.append(f'  - "{r}"')
        blocos.append("")

    if ganchos:
        blocos.append("TIPOS DE GANCHO JA USADOS (use uma abordagem nova):")
        for g in ganchos[-10:]:
            blocos.append(f'  - "{g}"')
        blocos.append("")

    if metaforas:
        blocos.append("METAFORAS/IMAGENS JA USADAS (crie novas):")
        for mt in metaforas[-10:]:
            blocos.append(f'  - "{mt}"')
        blocos.append("")

    if temas:
        blocos.append("TEMAS CENTRAIS JA ABORDADOS (use angulos diferentes):")
        for t in temas[-10:]:
            blocos.append(f'  - "{t}"')
        blocos.append("")

    if dialogos_exemplos:
        blocos.append("DIALOGOS/GANCHOS JA USADOS (crie falas INEDITAS):")
        for d in dialogos_exemplos[-10:]:
            blocos.append(f'  - "{d}..."')
        blocos.append("")

    blocos.append(
        "INSTRUCOES DE VARIACAO:\n"
        "- Escolha um LOCAL/CENARIO que NAO apareca na lista acima\n"
        "- Use METAFORAS e IMAGENS completamente novas\n"
        "- Varie o TOM EMOCIONAL (surpreendente, misterioso, provocador, terno, revelador)\n"
        "- Crie um GANCHO de abertura com estrutura diferente das anteriores\n"
        "- Mude detalhes visuais do personagem (roupa, acessorios, postura)\n"
    )

    return "\n".join(blocos)
