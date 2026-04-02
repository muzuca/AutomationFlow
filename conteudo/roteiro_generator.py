"""
Gerador de roteiros completos via Gemini API, suportando múltiplos personagens.

Uso típico (Ana):
    from conteudo.roteiro_generator import gerar_roteiro_ana

    roteiro = gerar_roteiro_ana(
        signo="Gêmeos",
        tema="comunicação e prosperidade",
        mensagem_central="usar a comunicação como dom para atrair sorte e dinheiro",
        n_cenas=5,
    )
    prompts = roteiro["prompts"]   # list[str] — prompts prontos para o Flow
"""

from typing import Dict, List

from .personas.ana_cartomante import (
    AUDIO_BLOCK as ANA_AUDIO_BLOCK,
    BACKGROUND_BLOCK as ANA_BACKGROUND_BLOCK,
    CHARACTER_BLOCK as ANA_CHARACTER_BLOCK,
    ESTRUTURA_CENAS as ANA_ESTRUTURA_CENAS,
    LIGHTING_BLOCK as ANA_LIGHTING_BLOCK,
    NOME as ANA_NOME,
    STYLE_BLOCK as ANA_STYLE_BLOCK,
    TECH_BLOCK as ANA_TECH_BLOCK,
    VOICE_STYLE as ANA_VOICE_STYLE,
)

from .personas.coach_espiritual import (
    AUDIO_BLOCK as COACH_AUDIO_BLOCK,
    BACKGROUND_BLOCK as COACH_BACKGROUND_BLOCK,
    CHARACTER_BLOCK as COACH_CHARACTER_BLOCK,
    ESTRUTURA_CENAS as COACH_ESTRUTURA_CENAS,
    LIGHTING_BLOCK as COACH_LIGHTING_BLOCK,
    NOME as COACH_NOME,
    STYLE_BLOCK as COACH_STYLE_BLOCK,
    TECH_BLOCK as COACH_TECH_BLOCK,
    VOICE_STYLE as COACH_VOICE_STYLE,
)

from .roteiro_core import (
    gerar_roteiro_generico,
    _contar_palavras,
)


# ── MONTADORES DE PROMPT VEO3 ────────────────────────────────────────────────


def _montar_prompt_veo3_ana(cena: dict, dialogo: str) -> str:
    dialogo_seguro = dialogo.replace('"', "'")
    return (
        "Subject: A hyper-realistic cinematic selfie video of a Brazilian fortune teller "
        f"named {ANA_NOME} walking through an open city square with colorful trees and a central "
        f"fountain during golden hour, {cena['subject_suffix']}\n\n"
        f"{ANA_CHARACTER_BLOCK}\n\n"
        f"{ANA_BACKGROUND_BLOCK}\n\n"
        f"{ANA_LIGHTING_BLOCK}\n\n"
        f"Action: {cena['action']}\n\n"
        f"{ANA_STYLE_BLOCK}\n\n"
        f"Dialogue: spoken in Brazilian Portuguese [{ANA_VOICE_STYLE}, {cena['tone']}]\n"
        f"\"{dialogo_seguro}\"\n\n"
        f"{ANA_AUDIO_BLOCK}\n"
        f"{ANA_TECH_BLOCK}"
    )


def _montar_prompt_veo3_coach(cena: dict, dialogo: str) -> str:
    dialogo_seguro = dialogo.replace('"', "'")
    return (
        "Subject: A hyper-realistic cinematic video of a serene Brazilian spiritual life coach "
        f"named {COACH_NOME} standing in a small cozy apartment kitchen in the early morning, "
        f"{cena['subject_suffix']}\n\n"
        f"{COACH_CHARACTER_BLOCK}\n\n"
        f"{COACH_BACKGROUND_BLOCK}\n\n"
        f"{COACH_LIGHTING_BLOCK}\n\n"
        f"Action: {cena['action']}\n\n"
        f"{COACH_STYLE_BLOCK}\n\n"
        f"Dialogue: spoken in Brazilian Portuguese [{COACH_VOICE_STYLE}, {cena['tone']}]\n"
        f"\"{dialogo_seguro}\"\n\n"
        f"{COACH_AUDIO_BLOCK}\n"
        f"{COACH_TECH_BLOCK}"
    )


# ── VALIDAÇÃO DE DIÁLOGOS ───────────────────────────────────────────────────


def _validar_dialogos_ana(cenas_json: list) -> list[str]:
    avisos = []
    for c in cenas_json:
        n = _contar_palavras(c.get("dialogo", ""))
        if not (20 <= n <= 24):
            avisos.append(
                f"  ⚠ Cena {c['numero']} ({c['nome']}): {n} palavras "
                f"(esperado ~22) — '{c['dialogo'][:60]}...'"
            )
    return avisos


def _validar_dialogos_coach(cenas_json: list) -> list[str]:
    avisos = []
    for c in cenas_json:
        n = _contar_palavras(c.get("dialogo", ""))
        if n != 19:
            avisos.append(
                f"  ⚠ Cena {c['numero']} ({c['nome']}): {n} palavras "
                f"(esperado 19) — '{c['dialogo'][:60]}...'"
            )
    return avisos


# ── GERADORES ESPECÍFICOS DE ROTEIRO ────────────────────────────────────────


def gerar_roteiro_ana(
    signo: str,
    tema: str,
    mensagem_central: str,
    n_cenas: int = 5,
) -> Dict:
    """
    Gera um roteiro completo para Ana Cartomante com N cenas.
    """
    instrucao_sistema = """Você é um especialista em criação de roteiros para vídeos virais de cartomantes no Instagram e TikTok.
Você conhece profundamente o estilo da Ana Cartomante: energética, Carioca, carismática, direta e espiritual.
Seus roteiros sempre geram alto engajamento porque combinam identificação emocional, revelação de dom/desafio e CTA poderoso.
Responda SEMPRE em JSON válido, sem markdown, sem explicações fora do JSON."""

    descricao_cenas = "\n".join(
        [f"Cena {c['numero']} — {c['nome']}: {c['objetivo']}" for c in ANA_ESTRUTURA_CENAS]
    )

    mensagem_usuario = f"""Crie um roteiro de 5 cenas para Ana Cartomante com as seguintes informações:
- Signo: {signo}
- Tema: {tema}
- Mensagem central: {mensagem_central}

REGRAS OBRIGATÓRIAS:
1. Cada diálogo deve ter EXATAMENTE 22 palavras em português brasileiro
2. Use linguagem Carioca natural: "demais", "gigante", "né", "vem", "sempre", "super"
3. Proibido linguagem formal ou corporativa — fale como uma amiga empolgada
4. Cada texto_tela: máximo 5 palavras + 1 emoji relevante, tudo em MAIÚSCULAS
5. Progressão emocional obrigatória: hook → desafio → dom → conselho → CTA
6. O CTA da cena 5 DEVE pedir para comentar algo específico relacionado ao tema
7. Nos diálogos use APENAS aspas simples (') se precisar citar algo — NUNCA aspas duplas

ESTRUTURA DAS CENAS:
{descricao_cenas}

Retorne EXATAMENTE este JSON (sem mais nada, sem markdown):
{{
  "cenas": [
    {{
      "numero": 1,
      "nome": "A Revelação",
      "texto_tela": "TEXTO CURTO + EMOJI",
      "dialogo": "exatamente 22 palavras aqui"
    }},
    {{
      "numero": 2,
      "nome": "O Desafio",
      "texto_tela": "TEXTO CURTO + EMOJI",
      "dialogo": "exatamente 22 palavras aqui"
    }},
    {{
      "numero": 3,
      "nome": "A Transformação",
      "texto_tela": "TEXTO CURTO + EMOJI",
      "dialogo": "exatamente 22 palavras aqui"
    }},
    {{
      "numero": 4,
      "nome": "O Conselho",
      "texto_tela": "TEXTO CURTO + EMOJI",
      "dialogo": "exatamente 22 palavras aqui"
    }},
    {{
      "numero": 5,
      "nome": "O Chamado (CTA)",
      "texto_tela": "TEXTO CURTO + EMOJI",
      "dialogo": "exatamente 22 palavras aqui"
    }}
  ],
  "descricao": "descrição resumida do roteiro para caption — máx 2 frases",
  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"]
}}"""

    print(f"\n[ROTEIRO] Gerando roteiro — Ana | Signo: {signo} | Tema: {tema} | Cenas: {n_cenas}")

    return gerar_roteiro_generico(
        instrucao_sistema=instrucao_sistema,
        mensagem_usuario=mensagem_usuario,
        estrutura_cenas=ANA_ESTRUTURA_CENAS,
        n_cenas=n_cenas,
        builder_prompt_veo3=_montar_prompt_veo3_ana,
        validar_dialogos=_validar_dialogos_ana,
    )


def gerar_roteiro_coach(
    tema: str,
    mensagem_central: str,
    n_cenas: int = 3,
) -> Dict:
    """
    Gera um roteiro completo para o Coach Espiritual com N cenas (padrão 3).
    Cada diálogo deve ter exatamente 19 palavras.
    """
    instrucao_sistema = """Você é um especialista em criação de roteiros curtos e profundos para um Coach Espiritual brasileiro.
O Coach fala sobre superação, amor, fé e Deus, sempre com mensagens acolhedoras e bíblicas.
Os roteiros são usados em vídeos verticais curtos, com 3 cenas de 6 segundos cada.
Responda SEMPRE em JSON válido, sem markdown, sem explicações fora do JSON."""

    descricao_cenas = "\n".join(
        [f"Cena {c['numero']} — {c['nome']}: {c['objetivo']}" for c in COACH_ESTRUTURA_CENAS]
    )

    mensagem_usuario = f"""Crie um roteiro de 3 cenas para o Coach Espiritual com as seguintes informações:
- Tema geral: {tema}
- Mensagem central: {mensagem_central}

REGRAS OBRIGATÓRIAS:
1. Cada diálogo deve ter EXATAMENTE 19 palavras em português brasileiro
2. Linguagem simples, direta, espiritual, SEM jargão religioso complexo
3. Pode citar Deus, fé, oração e versículos de forma natural (sem referência numérica exata obrigatória)
4. Cada texto_tela: máximo 6 palavras, pode ter 1 emoji relevante
5. Progressão emocional: reconhecimento da dor → perspectiva em Deus → convite para respirar, entregar e seguir
6. No final da cena 3, peça para a pessoa comentar "Amém" ou algo de concordância

ESTRUTURA DAS CENAS:
{descricao_cenas}

Retorne EXATAMENTE este JSON (sem mais nada, sem markdown):
{{
  "cenas": [
    {{
      "numero": 1,
      "nome": "O Peso da Manhã",
      "texto_tela": "TEXTO CURTO + EMOJI",
      "dialogo": "exatamente 19 palavras aqui"
    }},
    {{
      "numero": 2,
      "nome": "Um Dia de Cada Vez",
      "texto_tela": "TEXTO CURTO + EMOJI",
      "dialogo": "exatamente 19 palavras aqui"
    }},
    {{
      "numero": 3,
      "nome": "Respira e Entrega",
      "texto_tela": "TEXTO CURTO + EMOJI",
      "dialogo": "exatamente 19 palavras aqui"
    }}
  ],
  "descricao": "descrição resumida do roteiro para caption — máx 2 frases",
  "hashtags": ["#hashtag1", "#hashtag2", "#hashtag3"]
}}"""

    print(f"\n[ROTEIRO] Gerando roteiro — Coach Espiritual | Tema: {tema} | Cenas: {n_cenas}")

    return gerar_roteiro_generico(
        instrucao_sistema=instrucao_sistema,
        mensagem_usuario=mensagem_usuario,
        estrutura_cenas=COACH_ESTRUTURA_CENAS,
        n_cenas=n_cenas,
        builder_prompt_veo3=_montar_prompt_veo3_coach,
        validar_dialogos=_validar_dialogos_coach,
    )


# ── GERAÇÃO EM LOTE (Apenas Ana por enquanto) ───────────────────────────────


def gerar_multiplos_roteiros_ana(
    signo: str,
    temas: List[str],
    mensagens: List[str],
    n_cenas: int = 5,
) -> List[Dict]:
    if len(temas) != len(mensagens):
        raise ValueError("temas e mensagens devem ter o mesmo número de itens.")

    roteiros: List[Dict] = []
    for i, (tema, mensagem) in enumerate(zip(temas, mensagens), start=1):
        print(f"\n{'='*50}")
        print(f"  ROTEIRO {i}/{len(temas)} — Ana | {signo} | {tema}")
        print(f"{'='*50}")
        roteiro = gerar_roteiro_ana(
            signo=signo,
            tema=tema,
            mensagem_central=mensagem,
            n_cenas=n_cenas,
        )
        roteiros.append(roteiro)

    return roteiros