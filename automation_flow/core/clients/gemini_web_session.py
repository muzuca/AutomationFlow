# arquivo: automation_flow/core/clients/gemini_web_session.py
"""
Gerenciador de sessão do GeminiWebClient.

Responsável por:
- Ler as credenciais do .env (HUMBLE_EMAIL_1 + HUMBLE_PASSWORD_1 por padrão,
  ou FG_EMAIL/FG_SENHA como fallback — o mesmo email é usado no Google)
- Criar e guardar uma instância única do GeminiWebClient (singleton por processo)
- Expor get_session() para qualquer fluxo que precisar do Gemini

Uso:
    from automation_flow.core.clients.gemini_web_session import get_session

    gemini = get_session()
    gemini.login()
    resposta = gemini.enviar_prompt("Descreva este produto como um anúncio de TikTok")
"""

from __future__ import annotations

import os
import logging
from typing import Optional

from dotenv import load_dotenv

from automation_flow.core.clients.gemini_web_client import GeminiWebClient

load_dotenv()
logger = logging.getLogger(__name__)

_session_instance: Optional[GeminiWebClient] = None


def get_session(
    headless: bool = False,
    timeout: int = 40,
    conta_index: int = 1,
) -> GeminiWebClient:
    """
    Retorna a instância (singleton) do GeminiWebClient.

    Parâmetros
    ----------
    headless     : roda sem janela visível
    timeout      : tempo máximo de espera nas operações Selenium
    conta_index  : qual conta HUMBLE usar (1 a 8). Se a variável não existir,
                   cai no FG_EMAIL/FG_SENHA como alternativa.

    Notas
    -----
    - O Gemini usa a conta Google — por isso a conta HUMBLE_EMAIL_1 (que é
      um email Google) funciona aqui também.
    - A instância é reutilizada durante toda a execução. Chame .fechar()
      explicitamente quando quiser encerrar.
    """
    global _session_instance

    if _session_instance is not None:
        return _session_instance

    # Tenta HUMBLE_EMAIL_{n} primeiro
    email = os.getenv(f"HUMBLE_EMAIL_{conta_index}")
    senha = os.getenv(f"HUMBLE_PASSWORD_{conta_index}")

    # Fallback: FG_EMAIL / FG_SENHA
    if not email or not senha:
        email = os.getenv("FG_EMAIL")
        senha = os.getenv("FG_SENHA")

    if not email or not senha:
        raise EnvironmentError(
            "[GeminiWebSession] Nenhuma credencial encontrada. "
            f"Configure HUMBLE_EMAIL_{conta_index}/HUMBLE_PASSWORD_{conta_index} "
            "ou FG_EMAIL/FG_SENHA no .env"
        )

    logger.info("[GeminiWebSession] Usando conta: %s", email)

    _session_instance = GeminiWebClient(
        email=email,
        password=senha,
        timeout=timeout,
        headless=headless,
    )
    return _session_instance


def resetar_session() -> None:
    """Fecha e descarta a sessão atual (útil para troca de conta ou restart)."""
    global _session_instance
    if _session_instance:
        _session_instance.fechar()
        _session_instance = None
    logger.info("[GeminiWebSession] Sessão resetada.")
