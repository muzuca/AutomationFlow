"""
arquivo: conteudo/core.py
descrição: Núcleo consolidado de conteúdo. Gerencia a geração de roteiros via IA, o histórico em JSON para evitar repetições e o agendamento de janelas de publicação.
"""

import json
import re
import time
from typing import Dict, List, Any, Callable, Optional
from pathlib import Path
from datetime import datetime, timedelta
from difflib import SequenceMatcher

# Import da integração com Gemini
from integrations.gemini import gerar_com_rotacao_json

# --- CONFIGURAÇÕES DE HISTÓRICO E SCHEDULER ---
BASE_DIR = Path(__file__).resolve().parent.parent
HISTORICO_PATH = BASE_DIR / "historico_roteiros.json"

LIMIAR_SIMILARIDADE = 0.75
JANELA_COMPARACAO = 20
HORARIOS_PUBLICACAO = [9, 12, 17, 19, 21]
ANTECEDENCIA_HORAS = 1.5

# ============================================================================
#   LÓGICA DE ROTEIROS (ROTEIRO_CORE)
# ============================================================================

def contar_palavras(texto: str) -> int:
    """Conta palavras relevantes ignorando conectores curtos."""
    if not texto: return 0
    palavras = (texto or "").split()
    n = 0
    for p in palavras:
        limpa = "".join(ch for ch in p.lower() if ch.isalpha())
        if len(limpa) <= 2: continue
        n += 1
    return n

def _limpar_resposta(texto: Any) -> str:
    """Remove blocos de código markdown e extrai apenas o JSON."""
    if texto is None: return ""
    texto = str(texto).strip()
    if texto.startswith("```"):
        partes = texto.split("```")
        for p in partes:
            p = p.strip()
            if p.lower().startswith("json"): p = p[4:].strip()
            if p.startswith("{") or p.startswith("["):
                texto = p
                break
    return texto

def gerar_roteiro_generico(
    instrucao_sistema: str,
    mensagem_usuario: str,
    estrutura_cenas: List[dict],
    n_cenas: int,
    builder_prompt_veo3: Callable[[dict, str], str],
    validar_dialogos: Optional[Callable] = None,
    min_palavras: int = 14,
    max_palavras: int = 25,
) -> Dict[str, Any]:
    """Motor central para geração e validação de roteiros com retentativas."""
    tentativas = 6
    ultimo_erro_feedback = None

    for tentativa in range(1, tentativas + 1):
        try:
            msg_envio = mensagem_usuario
            if ultimo_erro_feedback:
                msg_envio += f"\n\nIMPORTANTE: Corrija os erros anteriores:\n{ultimo_erro_feedback}"

            texto_bruto = gerar_com_rotacao_json(
                mensagem_usuario=msg_envio,
                instrucao_sistema=instrucao_sistema,
                max_output_tokens=4096,
                temperature=0.9,
            )

            texto = _limpar_resposta(texto_bruto)
            dados = json.loads(texto)
            cenas_json = dados["cenas"][:n_cenas]

            prompts, dialogos, textos_tela = [], [], []
            for i, cena_dados in enumerate(cenas_json):
                dialogo = (cena_dados.get("dialogo", "")).strip()
                prompt_completo = builder_prompt_veo3(estrutura_cenas[i], dialogo)
                prompts.append(prompt_completo)
                dialogos.append(dialogo)
                textos_tela.append(cena_dados.get("texto_tela", ""))

            return {
                "prompts": prompts, "dialogos": dialogos, "textos_tela": textos_tela,
                "descricao": dados.get("descricao", ""), "hashtags": dados.get("hashtags", []),
                "cenas": cenas_json
            }

        except Exception as e:
            print(f"  ⚠ Tentativa {tentativa}/{tentativas} falhou: {e}")
            ultimo_erro_feedback = f"Erro no JSON ou tamanho de diálogo fora da faixa."
            time.sleep(3)

    raise RuntimeError("Falha definitiva na geração do roteiro.")

# ============================================================================
#   LÓGICA DE HISTÓRICO (HISTORICO)
# ============================================================================

def _carregar_historico() -> list[dict]:
    if not HISTORICO_PATH.exists(): return []
    try:
        with open(HISTORICO_PATH, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else []
    except Exception: return []

def registrar_roteiro(personagem: str, signo: str, tema: str, roteiro: dict):
    """Salva o roteiro gerado no arquivo JSON."""
    historico = _carregar_historico()
    historico.append({
        "timestamp":  time.strftime("%Y-%m-%d %H:%M:%S"),
        "personagem": personagem,
        "signo":      signo,
        "tema":       tema,
        "descricao":  roteiro.get("descricao", ""),
        "dialogos":   roteiro.get("dialogos", []),
        "hashtags":   roteiro.get("hashtags", []),
    })
    with open(HISTORICO_PATH, "w", encoding="utf-8") as f:
        json.dump(historico, f, ensure_ascii=False, indent=2)

def roteiro_e_repetido(personagem: str, tema: str, roteiro: dict) -> bool:
    """Verifica similaridade com os últimos roteiros gerados."""
    historico = _carregar_historico()
    recentes = [h for h in historico if h.get("personagem") == personagem and h.get("tema") == tema][-JANELA_COMPARACAO:]
    if not recentes: return False

    texto_novo = f"{roteiro.get('descricao', '')} {' '.join(roteiro.get('dialogos', []))}".lower()
    for ant in recentes:
        texto_ant = f"{ant.get('descricao', '')} {' '.join(ant.get('dialogos', []))}".lower()
        if SequenceMatcher(None, texto_novo, texto_ant).ratio() >= LIMIAR_SIMILARIDADE:
            print(f"  ⚠ Roteiro similar detectado.")
            return True
    return False

# ============================================================================
#   LÓGICA DE AGENDAMENTO (SCHEDULER)
# ============================================================================

def calcular_proxima_janela() -> datetime:
    """Retorna o início da próxima janela com base nos horários de publicação."""
    agora = datetime.now()
    for hora in sorted(HORARIOS_PUBLICACAO):
        janela = agora.replace(hour=hora, minute=0, second=0, microsecond=0) - timedelta(hours=ANTECEDENCIA_HORAS)
        if janela > agora: return janela
    
    amanha = agora + timedelta(days=1)
    primeira = sorted(HORARIOS_PUBLICACAO)[0]
    return amanha.replace(hour=primeira, minute=0, second=0, microsecond=0) - timedelta(hours=ANTECEDENCIA_HORAS)

def aguardar_proxima_janela():
    """Pausa o script até o próximo horário de geração."""
    proxima = calcular_proxima_janela()
    espera = (proxima - datetime.now()).total_seconds()
    if espera <= 0: return

    print(f"\n  ⏰ Próxima janela: {proxima.strftime('%d/%m %H:%M')}")
    print(f"  ⏳ Aguardando {int(espera // 3600)}h {int((espera % 3600) // 60)}min...")
    
    while datetime.now() < proxima:
        resta = (proxima - datetime.now()).total_seconds()
        time.sleep(min(60, resta) if resta > 10 else resta)