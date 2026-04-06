# arquivo: automation_flow/core/clients/gemini_web_client.py
"""
Client para usar o Gemini Web (https://gemini.google.com/app) reaproveitando
o mesmo driver já logado no Flow/Humble.

IMPORTANTE:
- Este client NÃO faz login Google.
- Ele assume que o driver já está autenticado na conta Google (porque o
  fluxo do Humble já abriu o Flow e fez login).
- Deve ser usado passando o `driver` retornado por `_abrir_conta` em
  `humble_orchestrator.py`.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime

from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

GEMINI_APP_URL = "https://gemini.google.com/app"

# Seletor genérico do campo de prompt do Gemini (pode ser ajustado depois
# que você me mandar um print/HTML da interface).
_PROMPT_SELECTOR = (
    By.CSS_SELECTOR,
    "div[contenteditable='true'], textarea[aria-label]",
)

_RESPONSE_SELECTOR = (
    By.CSS_SELECTOR,
    "model-response, .response-content, message-content",
)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(msg: str) -> None:
    print(f"[{_ts()}] {msg}")


@dataclass
class GeminiWebClient:
    """Client simples para operar o Gemini Web usando um WebDriver existente.

    driver   : instância já logada na conta Google (a mesma do Flow)
    timeout  : tempo máximo de espera
    """

    driver: WebDriver
    timeout: int = 30

    # ------------------------------------------------------------------
    #  ABERTURA / PREPARO
    # ------------------------------------------------------------------

    def abrir(self) -> None:
        """Abre o Gemini Web em uma nova aba usando o mesmo driver.

        Se já houver uma aba com gemini.google.com aberta, apenas troca o foco
        para ela.
        """
        _log("[GEMINI] Procurando aba existente do Gemini...")
        for handle in self.driver.window_handles:
            self.driver.switch_to.window(handle)
            try:
                url = (self.driver.current_url or "").lower()
            except Exception:
                url = ""
            if "gemini.google.com" in url:
                _log(f"[GEMINI] Aba existente encontrada: {url}")
                return

        _log(f"[GEMINI] Nenhuma aba do Gemini encontrada. Abrindo nova aba em {GEMINI_APP_URL}...")
        self.driver.switch_to.new_window("tab")
        self.driver.get(GEMINI_APP_URL)

        wait = WebDriverWait(self.driver, self.timeout)
        self._esperar_prompt(wait)

    # ------------------------------------------------------------------
    #  Métodos internos
    # ------------------------------------------------------------------

    def _esperar_prompt(self, wait: WebDriverWait) -> None:
        """Espera o campo de prompt aparecer (ou falha silenciosamente)."""
        _log("[GEMINI] Aguardando campo de prompt ficar visível...")
        try:
            wait.until(EC.visibility_of_element_located(_PROMPT_SELECTOR))
            _log("[GEMINI] Campo de prompt visível.")
        except TimeoutException:
            _log("[GEMINI] ⚠ Timeout aguardando campo de prompt. Seguindo mesmo assim.")

    def _capturar_resposta(self, wait: WebDriverWait) -> str:
        """Aguarda a resposta do Gemini estabilizar e retorna o texto."""
        _log("[GEMINI] Aguardando início da resposta...")
        try:
            wait.until(EC.presence_of_element_located(_RESPONSE_SELECTOR))
        except TimeoutException:
            _log("[GEMINI] ⚠ Timeout aguardando qualquer bloco de resposta.")
            return ""

        texto_anterior = ""
        estavel_por = 0
        max_espera = self.timeout

        _log("[GEMINI] Aguardando resposta estabilizar (streaming)...")
        for _ in range(max_espera):
            time.sleep(1)
            blocos = self.driver.find_elements(*_RESPONSE_SELECTOR)
            texto_atual = blocos[-1].text if blocos else ""

            if texto_atual and texto_atual == texto_anterior:
                estavel_por += 1
                if estavel_por >= 3:
                    _log("[GEMINI] Resposta estabilizada (sem mudanças por 3s).")
                    break
            else:
                estavel_por = 0
                texto_anterior = texto_atual

        final = texto_anterior or ""
        _log(f"[GEMINI] Resposta final capturada com {len(final)} caracteres.")
        return final

    # ------------------------------------------------------------------
    #  API pública
    # ------------------------------------------------------------------

    def enviar_prompt(self, texto: str, aguardar_resposta: bool = True) -> str:
        """Envia um prompt de texto para o Gemini.

        Retorna o texto da resposta (ou string vazia se não conseguir).
        """
        resumo = (texto[:120] + "...") if len(texto) > 120 else texto
        _log(f"[GEMINI] Preparando envio de prompt ({len(texto)} chars): {resumo!r}")

        wait = WebDriverWait(self.driver, self.timeout)

        _log("[GEMINI] Localizando campo de prompt para digitar...")
        campo = wait.until(EC.element_to_be_clickable(_PROMPT_SELECTOR))
        _log("[GEMINI] Campo de prompt clicável. Focando...")
        campo.click()
        time.sleep(0.2)

        _log("[GEMINI] Limpando conteúdo anterior (CTRL+A + BACKSPACE)...")
        try:
            campo.send_keys(Keys.CONTROL, "a")
            time.sleep(0.1)
            campo.send_keys(Keys.BACKSPACE)
            time.sleep(0.1)
        except Exception:
            _log("[GEMINI] ⚠ Não foi possível limpar o campo (ignorando).")

        _log("[GEMINI] Digitando prompt...")
        campo.send_keys(texto)
        time.sleep(0.2)

        _log("[GEMINI] Enviando prompt (ENTER)...")
        campo.send_keys(Keys.RETURN)

        if not aguardar_resposta:
            _log("[GEMINI] Configurado para NÃO aguardar resposta. Retornando string vazia.")
            return ""

        return self._capturar_resposta(wait)