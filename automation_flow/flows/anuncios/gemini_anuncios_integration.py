# arquivo: automation_flow/flows/anuncios/gemini_anuncios_integration.py
"""
Integração do Gemini Web com o fluxo de anúncios, reaproveitando
o mesmo driver do Humble/Flow.

Uso típico (dentro de humble_orchestrator, modo anúncios):

    from automation_flow.flows.anuncios.gemini_anuncios_integration import (
        GeminiAnunciosViaFlow,
    )

    driver = _abrir_conta(conta)  # já faz login no Flow
    gemini = GeminiAnunciosViaFlow(driver)
    gemini.abrir_gemini()
    roteiro = gemini.gerar_roteiro_anuncio("Nome do produto", [...])
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from selenium.webdriver.remote.webdriver import WebDriver

from automation_flow.core.clients.gemini_web_client import GeminiWebClient


_TEMPLATE_ROTEIRO_TIKTOK = """Você é um especialista em anúncios para TikTok Shop.

Produto: {nome}
Benefícios principais: {beneficios}
Tom desejado: {tom}
Duração alvo do vídeo: {duracao}s

Escreva um roteiro de vídeo curto para TikTok com:
- Gancho inicial em até 3 segundos
- Apresentação rápida do produto
- 3 bullets (benefícios) focados em dor → solução
- CTA final chamando para comprar na TikTok Shop

Use marcações [GANCHO], [PRODUTO], [BULLETS], [CTA].
Responda apenas com o roteiro, sem explicações extras.
"""


@dataclass
class GeminiAnunciosViaFlow:
    """Fachada de alto nível para usar o Gemini Web no fluxo de anúncios.

    driver : WebDriver já logado no Flow/Humble
    """

    driver: WebDriver
    timeout: int = 30

    def __post_init__(self) -> None:
        self._client = GeminiWebClient(self.driver, timeout=self.timeout)

    # ------------------------------------------------------------------
    #  Abertura do Gemini
    # ------------------------------------------------------------------

    def abrir_gemini(self) -> None:
        """Abre o Gemini Web em uma nova aba usando o mesmo driver."""
        self._client.abrir()

    # ------------------------------------------------------------------
    #  Roteiro de anúncio TikTok Shop
    # ------------------------------------------------------------------

    def gerar_roteiro_anuncio(
        self,
        nome_produto: str,
        beneficios: List[str],
        tom: str = "descontraído e direto",
        duracao: int = 25,
    ) -> str:
        """Pede ao Gemini um roteiro de anúncio para TikTok Shop."""
        self.abrir_gemini()

        prompt = _TEMPLATE_ROTEIRO_TIKTOK.format(
            nome=nome_produto,
            beneficios=", ".join(beneficios),
            tom=tom,
            duracao=duracao,
        )

        resposta = self._client.enviar_prompt(prompt, aguardar_resposta=True)
        return resposta or ""