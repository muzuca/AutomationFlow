# arquivo: test_gemini_via_flow.py
"""
Teste de integração Humble (Flow) + Gemini Web na MESMA sessão do navegador.

Uso:
    python test_gemini_via_flow.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
import os

from dotenv import load_dotenv

from acesso_humble import sincronizar_credenciais_humble
from automation_flow.core.flow import humble_orchestrator as ho
from automation_flow.core.clients.humble_client import (
    criar_driver_humble,
    fluxo_login_simples_sem_preparo,
)
from automation_flow.flows.anuncios.gemini_anuncios_integration import (
    GeminiAnunciosViaFlow,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stdout,
)


def carregar_contas_do_env() -> list[dict]:
    """Lê HUMBLE_EMAIL_N / HUMBLE_PASSWORD_N diretamente do .env."""
    env_path = Path(".env")
    load_dotenv(dotenv_path=env_path, override=True)

    contas: list[dict] = []

    for i in range(1, 50):
        email = os.getenv(f"HUMBLE_EMAIL_{i}")
        senha = os.getenv(f"HUMBLE_PASSWORD_{i}")

        if email and senha:
            contas.append(
                {
                    "indice": i,
                    "email": email.strip(),
                    "senha": senha.strip(),
                }
            )

    return contas


def preparar_contas_humble() -> None:
    """Sincroniza Google Doc -> .env e popula HUMBLE_ACCOUNTS para o teste."""
    print("Sincronizando credenciais Humble com o Google Doc...")
    sincronizar_credenciais_humble()

    print("Lendo contas diretamente do .env...")
    contas = carregar_contas_do_env()

    ho.HUMBLE_ACCOUNTS.clear()
    ho.HUMBLE_ACCOUNTS.extend(contas)

    print(f"{len(ho.HUMBLE_ACCOUNTS)} conta(s) Humble carregada(s).")


def _pegar_primeira_conta_ativa() -> dict:
    """Retorna a primeira conta Humble disponível."""
    if not ho.HUMBLE_ACCOUNTS:
        raise RuntimeError("Nenhuma conta Humble encontrada no .env")
    return ho.HUMBLE_ACCOUNTS[0]


def main() -> None:
    print("\n=== TESTE HUMBLE + GEMINI WEB (MESMO DRIVER) ===\n")

    preparar_contas_humble()

    conta = _pegar_primeira_conta_ativa()
    print(f"Usando conta Humble índice={conta['indice']} email={conta['email']}")

    driver = None
    try:
        # NOVO: cria driver e faz apenas login simples no Flow
        driver = criar_driver_humble()
        fluxo_login_simples_sem_preparo(driver, conta["email"], conta["senha"])

        # Cria fachada do Gemini para essa sessão (mesmo driver)
        gemini = GeminiAnunciosViaFlow(driver)

        # Gera roteiro de anúncio de teste
        roteiro = gemini.gerar_roteiro_anuncio(
            nome_produto="Absorvente Lara Select Orgânico",
            beneficios=[
                "100% algodão orgânico, mais conforto",
                "sem perfume e sem substâncias tóxicas",
                "proteção segura para o dia a dia",
            ],
            tom="feminino, empático e direto",
            duracao=25,
        )

        print("\n──── ROTEIRO GERADO PELO GEMINI ───────────────────────────────")
        print(roteiro)
        print("───────────────────────────────────────────────────────────────\n")

    finally:
        if driver is not None:
            try:
                driver.quit()
            except Exception:
                pass
        print("Teste concluído. Driver fechado.")


if __name__ == "__main__":
    main()