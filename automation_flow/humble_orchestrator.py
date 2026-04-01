from datetime import datetime
from pathlib import Path

from .config import HUMBLE_ACCOUNTS
from .humble_client import (
    criar_driver_humble,
    fluxo_completo_login_e_preparo,
    gerar_video_humble,
    HumbleFlowError,
)


def _ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(msg: str):
    print(f"[{_ts()}] {msg}")


def main(prompts: list[str]) -> list[Path]:
    print("=" * 55)
    print("  AUTOMAÇÃO HUMBLE → FLOW WEB")
    print("=" * 55)

    if not HUMBLE_ACCOUNTS:
        raise ValueError("Nenhuma conta HUMBLE_EMAIL_N / HUMBLE_PASSWORD_N encontrada no .env")

    if not prompts:
        _log("ℹ Nenhum prompt recebido.")
        return []

    ultimo_erro = None

    for conta in HUMBLE_ACCOUNTS:
        idx = conta["indice"]
        email = conta["email"]
        senha = conta["senha"]

        _log(f"[CONTA #{idx}] Tentando conta: {email}")
        driver = None

        try:
            driver = criar_driver_humble()
            fluxo_completo_login_e_preparo(driver, email, senha)

            for i, prompt in enumerate(prompts, 1):
                _log(f"[VIDEO {i}/{len(prompts)}]")
                _log(f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
                gerar_video_humble(driver, prompt)

            _log(f"✔ Conta #{idx} funcionou.")
            return []

        except Exception as e:
            ultimo_erro = e
            _log(f"❌ Conta #{idx} falhou: {e}")

        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    raise HumbleFlowError(f"Todas as contas Humble falharam. Último erro: {ultimo_erro}")