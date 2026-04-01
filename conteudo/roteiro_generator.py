"""
Gerador de roteiros completos para Ana Cartomante via Gemini API.

Uso:
    from conteudo.roteiro_generator import gerar_roteiro

    roteiro = gerar_roteiro(
        signo="Gêmeos",
        tema="comunicação e prosperidade",
        mensagem_central="usar a comunicação como dom para atrair sorte e dinheiro",
        n_cenas=5,
    )
    prompts = roteiro["prompts"]   # list[str] — prompts prontos para o Flow
"""

import json
import time
from typing import Dict, List

from .personagens.ana_cartomante import (
    AUDIO_BLOCK,
    BACKGROUND_BLOCK,
    CHARACTER_BLOCK,
    ESTRUTURA_CENAS,
    LIGHTING_BLOCK,
    NOME,
    STYLE_BLOCK,
    TECH_BLOCK,
    VOICE_STYLE,
)
from automation_flow.gemini_client import gerar_com_rotacao_json


# ── Helpers internos ─────────────────────────────────────────────────────────


def _montar_prompt_veo3(cena: dict, dialogo: str) -> str:
    dialogo_seguro = dialogo.replace('"', "'")
    return (
        f"Subject: A hyper-realistic cinematic selfie video of a Brazilian fortune teller "
        f"named {NOME} walking through an open city square with colorful trees and a central "
        f"fountain during golden hour, {cena['subject_suffix']}\n\n"
        f"{CHARACTER_BLOCK}\n\n"
        f"{BACKGROUND_BLOCK}\n\n"
        f"{LIGHTING_BLOCK}\n\n"
        f"Action: {cena['action']}\n\n"
        f"{STYLE_BLOCK}\n\n"
        f"Dialogue: spoken in Brazilian Portuguese [{VOICE_STYLE}, {cena['tone']}]\n"
        f'"{dialogo_seguro}"\n\n'
        f"{AUDIO_BLOCK}\n"
        f"{TECH_BLOCK}"
    )


def _contar_palavras(texto: str) -> int:
    return len(texto.split())


def _validar_dialogos(cenas_json: list) -> list[str]:
    avisos = []
    for c in cenas_json:
        n = _contar_palavras(c.get("dialogo", ""))
        if not (20 <= n <= 24):
            avisos.append(
                f"  ⚠ Cena {c['numero']} ({c['nome']}): {n} palavras "
                f"(esperado ~22) — '{c['dialogo'][:60]}...'"
            )
    return avisos


def _parse_json_seguro(texto: str) -> dict:
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    texto_corrigido = texto
    abertos_colchete = texto.count("[") - texto.count("]")
    abertos_chave = texto.count("{") - texto.count("}")

    for _ in range(abertos_colchete):
        texto_corrigido += "]"
    for _ in range(abertos_chave):
        texto_corrigido += "}"

    try:
        dados = json.loads(texto_corrigido)
        print("  ⚠ JSON corrigido automaticamente (estava truncado).")
        return dados
    except json.JSONDecodeError as e:
        raise e


def _limpar_resposta(texto: str) -> str:
    texto = texto.strip()
    if texto.startswith("```"):
        partes = texto.split("```")
        texto = partes[1]
        if texto.startswith("json"):
            texto = texto[4:]
    return texto.strip()


# ── Geração principal ────────────────────────────────────────────────────────


def gerar_roteiro(
    signo: str,
    tema: str,
    mensagem_central: str,
    n_cenas: int = 5,
) -> Dict:
    """
    Gera um roteiro completo para Ana Cartomante com N cenas.
    """
    if n_cenas < 1:
        raise ValueError("n_cenas deve ser pelo menos 1.")
    if n_cenas > len(ESTRUTURA_CENAS):
        raise ValueError(f"n_cenas máximo suportado é {len(ESTRUTURA_CENAS)}.")

    instrucao_sistema = """Você é um especialista em criação de roteiros para vídeos virais de cartomantes no Instagram e TikTok.
Você conhece profundamente o estilo da Ana Cartomante: energética, Carioca, carismática, direta e espiritual.
Seus roteiros sempre geram alto engajamento porque combinam identificação emocional, revelação de dom/desafio e CTA poderoso.
Responda SEMPRE em JSON válido, sem markdown, sem explicações fora do JSON."""

    descricao_cenas = "\n".join(
        [f"Cena {c['numero']} — {c['nome']}: {c['objetivo']}" for c in ESTRUTURA_CENAS]
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

    print(f"\n[ROTEIRO] Gerando roteiro — Signo: {signo} | Tema: {tema} | Cenas: {n_cenas}")

    tentativas = 3
    for tentativa in range(1, tentativas + 1):
        try:
            texto_bruto = gerar_com_rotacao_json(
                mensagem_usuario=mensagem_usuario,
                instrucao_sistema=instrucao_sistema,
                max_output_tokens=4096,
                temperature=0.9,
            )

            texto = _limpar_resposta(texto_bruto)
            dados = _parse_json_seguro(texto)

            cenas_json = dados["cenas"][:n_cenas]

            avisos = _validar_dialogos(cenas_json)
            for aviso in avisos:
                print(aviso)

            prompts: List[str] = []
            dialogos: List[str] = []
            textos_tela: List[str] = []

            for i, cena_dados in enumerate(cenas_json):
                cena_base = ESTRUTURA_CENAS[i]
                dialogo = cena_dados["dialogo"]
                texto_tela = cena_dados["texto_tela"]

                prompt_completo = _montar_prompt_veo3(cena_base, dialogo)
                prompts.append(prompt_completo)
                dialogos.append(dialogo)
                textos_tela.append(texto_tela)

                print(
                    f"  ✔ Cena {i + 1} — {cena_base['nome']}: {texto_tela}\n"
                    f"     Diálogo ({_contar_palavras(dialogo)} palavras): {dialogo}"
                )

            print(f"\n  📝 Descrição: {dados['descricao']}")
            print(f"  🏷  Hashtags:  {' '.join(dados['hashtags'])}")

            return {
                "prompts": prompts,
                "dialogos": dialogos,
                "textos_tela": textos_tela,
                "descricao": dados["descricao"],
                "hashtags": dados["hashtags"],
            }

        except json.JSONDecodeError as e:
            print(f"  ⚠ Tentativa {tentativa}/{tentativas} — JSON inválido: {e}")
            print(f"  ℹ Início da resposta: {texto_bruto[:200]!r}")
            if tentativa < tentativas:
                time.sleep(3)

        except Exception as e:
            print(f"  ⚠ Tentativa {tentativa}/{tentativas} falhou: {e}")
            if tentativa < tentativas:
                time.sleep(3)

    raise RuntimeError(
        f"Não foi possível gerar o roteiro para {signo}/{tema} após {tentativas} tentativas."
    )


# ── Geração em lote ──────────────────────────────────────────────────────────


def gerar_multiplos_roteiros(
    signo: str,
    temas: list[str],
    mensagens: list[str],
    n_cenas: int = 5,
) -> list[Dict]:
    if len(temas) != len(mensagens):
        raise ValueError("temas e mensagens devem ter o mesmo número de itens.")

    roteiros: list[Dict] = []
    for i, (tema, mensagem) in enumerate(zip(temas, mensagens), start=1):
        print(f"\n{'='*50}")
        print(f"  ROTEIRO {i}/{len(temas)} — {signo} | {tema}")
        print(f"{'='*50}")
        roteiro = gerar_roteiro(
            signo=signo,
            tema=tema,
            mensagem_central=mensagem,
            n_cenas=n_cenas,
        )
        roteiros.append(roteiro)
        if i < len(temas):
            time.sleep(2)

    return roteiros