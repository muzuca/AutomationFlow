"""
arquivo: integrations/gemini.py
descrição: Gerencia a integração com a API do Google Gemini, incluindo a configuração do modelo, 
           tratamento de segurança, detecção de erros de quota e rotação automática de chaves.
"""

import os
import re
import time
from pathlib import Path
from typing import List, Optional

from google import genai
from google.genai import types

# --- CONFIGURAÇÕES DE API ---
_GEMINI_API_KEYS_RAW = os.getenv("GEMINI_API_KEYS", "")
_GEMINI_API_KEYS: List[str] = [k.strip() for k in _GEMINI_API_KEYS_RAW.split(",") if k.strip()]

if not _GEMINI_API_KEYS:
    unica = os.getenv("GEMINI_API_KEY", "").strip()
    if unica:
        _GEMINI_API_KEYS = [unica]

# Modelo conforme seu arquivo original
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


class GeminiKeyRotator:
    def __init__(self, keys: List[str], cooldown_padrao: int = 3600):
        if not keys:
            raise ValueError(
                "Nenhuma chave Gemini configurada. Defina GEMINI_API_KEYS ou GEMINI_API_KEY no .env."
            )
        self.keys = keys
        self.index = 0
        self.blocked_until = {k: 0.0 for k in keys}
        self.cooldown_padrao = cooldown_padrao

    def current_key(self) -> Optional[str]:
        agora = time.time()
        total = len(self.keys)
        for i in range(total):
            idx = (self.index + i) % total
            key = self.keys[idx]
            if agora >= self.blocked_until.get(key, 0.0):
                self.index = idx
                return key
        return None

    def mark_rate_limited(self, key: str, cooldown: Optional[int] = None):
        cd = cooldown if cooldown is not None else self.cooldown_padrao
        self.blocked_until[key] = time.time() + cd

    def rotate_and_get(self) -> Optional[str]:
        if not self.keys:
            return None
        self.index = (self.index + 1) % len(self.keys)
        return self.current_key()

    def total_keys(self) -> int:
        return len(self.keys)


_rotator = GeminiKeyRotator(_GEMINI_API_KEYS)


def _mask_key(key: str) -> str:
    if not key or len(key) < 10:
        return "***"
    return f"{key[:6]}...{key[-4:]}"


def _criar_cliente(api_key: Optional[str] = None) -> genai.Client:
    key = (api_key or _rotator.current_key() or "").strip()
    if not key:
        raise ValueError("Nenhuma chave Gemini disponível (todas em cooldown ou não configuradas).")
    return genai.Client(api_key=key)


def criar_cliente_gemini() -> genai.Client:
    return _criar_cliente()


def _eh_erro_quota(e: Exception) -> bool:
    msg = str(e)
    msg_lower = msg.lower()
    return (
        "resource_exhausted" in msg_lower
        or "429" in msg
        or "quota" in msg_lower
        or "rate limit" in msg_lower
        or "permission_denied" in msg_lower
        or "403" in msg
    )


def _extrair_retry_delay_segundos(e: Exception) -> Optional[int]:
    msg = str(e)

    padroes = [
        r"retryDelay['\"]?\s*:\s*['\"]?(\d+)s",
        r"retry in\s+(\d+(?:\.\d+)?)s",
        r"Please retry in\s+(\d+(?:\.\d+)?)s",
    ]

    for padrao in padroes:
        m = re.search(padrao, msg, flags=re.IGNORECASE)
        if m:
            try:
                valor = float(m.group(1))
                return max(1, int(valor) + 5)
            except Exception:
                pass

    return None


def _gerar_texto_com_rotacao(
    *,
    mensagem_usuario: str,
    instrucao_sistema: str,
    temperature: float,
    max_output_tokens: int,
) -> str:
    total_keys = _rotator.total_keys()
    tentativas_totais = total_keys if total_keys > 0 else 1
    ultima_excecao: Optional[Exception] = None

    for tentativa_global in range(1, tentativas_totais + 1):
        api_key = _rotator.current_key()
        if not api_key:
            raise RuntimeError("Todas as chaves Gemini estão em cooldown (RESOURCE_EXHAUSTED).")

        cliente = _criar_cliente(api_key=api_key)

        print(
            f"[GEMINI] Tentativa global {tentativa_global}/{tentativas_totais} | "
            f"chave index={_rotator.index} | {_mask_key(api_key)}"
        )

        try:
            resposta = cliente.models.generate_content(
                model=GEMINI_MODEL,
                contents=mensagem_usuario,
                config=types.GenerateContentConfig(
                    system_instruction=instrucao_sistema,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                ),
            )

            texto = (resposta.text or "").strip()
            if not texto:
                raise RuntimeError("Gemini retornou resposta vazia.")

            return texto

        except Exception as e:
            ultima_excecao = e
            print(f"  ⚠ Erro na chave atual {_mask_key(api_key)}: {e}")

            if _eh_erro_quota(e):
                retry_delay = _extrair_retry_delay_segundos(e)
                cooldown = retry_delay if retry_delay is not None else 3600

                print(
                    f"  ⚠ Quota/503 detectado. "
                    f"Aguardando 2s e rotacionando para a próxima chave..."
                )
                
                # ADICIONE A LINHA ABAIXO:
                time.sleep(2) 
                
                _rotator.mark_rate_limited(api_key, cooldown=cooldown)
                _rotator.rotate_and_get()
                continue

            raise

    raise RuntimeError(
        f"Não foi possível obter resposta do Gemini após testar todas as chaves. "
        f"Último erro: {ultima_excecao}"
    )


def gerar_com_rotacao_json(
    mensagem_usuario: str,
    instrucao_sistema: str,
    max_output_tokens: int = 4096,
    temperature: float = 0.9,
) -> str:
    """Função chamada pelo core.py"""
    return _gerar_texto_com_rotacao(
        mensagem_usuario=mensagem_usuario,
        instrucao_sistema=instrucao_sistema,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )


def gerar_prompt_video(
    personagem: str,
    cenario: str,
    tipo_mensagem: str,
    idioma: str = "pt-BR",
    duracao_segundos: int = 8,
) -> str:
    instrucao_sistema = (
        "Você é um especialista em criação de prompts para geração de vídeos com IA. "
        "Seu objetivo é criar prompts cinematográficos, detalhados e visualmente ricos "
        "para o Google Flow (Veo 3.1). "
        "O prompt deve descrever a cena de forma objetiva, em uma única frase ou parágrafo curto, "
        "sem usar aspas, sem explicações adicionais, apenas o prompt em si. "
        f"Responda sempre em {idioma}."
    )

    mensagem_usuario = (
        f"Crie um prompt de vídeo com as seguintes características:\n"
        f"- Personagem: {personagem}\n"
        f"- Cenário: {cenario}\n"
        f"- Tipo de mensagem/emoção: {tipo_mensagem}\n"
        f"- Duração aproximada: {duracao_segundos} segundos\n"
        f"- Formato: vertical 9:16 (estilo Reels/TikTok)\n\n"
        f"Retorne APENAS o prompt, sem introdução, sem explicação, sem aspas."
    )

    print("\n[GEMINI] Gerando prompt de vídeo...")
    print(f"  Personagem: {personagem}")
    print(f"  Cenário:    {cenario}")
    print(f"  Mensagem:   {tipo_mensagem}")
    print(f"  Chaves disponíveis: {_rotator.total_keys()}")

    texto = _gerar_texto_com_rotacao(
        mensagem_usuario=mensagem_usuario,
        instrucao_sistema=instrucao_sistema,
        temperature=0.85,
        max_output_tokens=300,
    )

    prompt = texto.strip().strip('"').strip("'")
    print(f"  ✔ Prompt gerado: {prompt!r}")
    return prompt


def gerar_lote_prompts(
    personagem: str,
    cenario: str,
    tipos_mensagem: list[str],
    idioma: str = "pt-BR",
    duracao_segundos: int = 8,
) -> list[str]:
    prompts: list[str] = []
    for tipo in tipos_mensagem:
        prompt = gerar_prompt_video(
            personagem=personagem,
            cenario=cenario,
            tipo_mensagem=tipo,
            idioma=idioma,
            duracao_segundos=duracao_segundos,
        )
        prompts.append(prompt)
        time.sleep(1)
    return prompts