# humble_orchestrator.py

from datetime import datetime
from pathlib import Path

from .config import HUMBLE_ACCOUNTS
from .humble_client import (
    criar_driver_humble,
    fluxo_completo_login_e_preparo,
    gerar_video_humble,
    HumbleFlowError,
)


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(msg: str):
    print(f"[{ts()}] {msg}")


def _abrir_conta(conta: dict):
    """
    Abre uma conta do Humble já logada e preparada no Flow.
    Retorna o driver pronto para gerar.
    """
    idx = conta["indice"]
    email = conta["email"]
    senha = conta["senha"]

    _log(f"[CONTA #{idx}] Inicializando conta: {email}")

    driver = criar_driver_humble()
    fluxo_completo_login_e_preparo(driver, email, senha)

    _log(f"[CONTA #{idx}] Flow pronto para gerar.")
    return driver


def _fechar_driver(driver):
    if driver:
        try:
            driver.quit()
        except Exception:
            pass


def main(prompts: list[str]) -> list[Path]:
    """
    Ponto de entrada do Humble.

    Lógica espelhada do Guru:
    - processa uma cena por vez;
    - mantém uma sessão/conta atual aberta;
    - tenta primeiro na sessão atual;
    - se falhar, fecha essa sessão e rotaciona para a próxima conta;
    - só passa para a próxima cena depois que a atual der certo.
    """
    print("=" * 55)
    print("  AUTOMAÇÃO HUMBLE → FLOW WEB")
    print("=" * 55)

    if not HUMBLE_ACCOUNTS:
        raise ValueError("Nenhuma conta HUMBLE_EMAIL_N / HUMBLE_PASSWORD_N encontrada no .env")

    if not prompts:
        _log("Nenhum prompt recebido. Retornando lista vazia.")
        return []

    arquivos_baixados: list[Path] = []
    ultimo_erro = None

    total_contas = len(HUMBLE_ACCOUNTS)
    indice_conta_atual = 0
    driver_atual = None
    conta_atual = None

    for idx_prompt, prompt in enumerate(prompts, 1):
        _log(f"[VÍDEO {idx_prompt}/{len(prompts)}]")
        _log(f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")

        gerou = False
        contas_tentadas_consecutivas = 0

        while not gerou:
            # Tenta primeiro na conta já aberta
            if driver_atual is not None and conta_atual is not None:
                try:
                    _log(f"[CONTA #{conta_atual['indice']}] Tentando gerar a cena atual...")
                    arquivo = gerar_video_humble(driver_atual, prompt)

                    if arquivo:
                        arquivos_baixados.append(arquivo)
                        _log(f"✔ Cena {idx_prompt} baixada: {arquivo.name}")
                        gerou = True
                        contas_tentadas_consecutivas = 0
                        break

                    _log(f"⚠ Conta #{conta_atual['indice']} não retornou arquivo. Rotacionando conta...")
                    _fechar_driver(driver_atual)
                    driver_atual = None
                    conta_atual = None

                except Exception as e:
                    ultimo_erro = e
                    _log(f"❌ Conta #{conta_atual['indice']} falhou na cena {idx_prompt}: {e}")
                    _fechar_driver(driver_atual)
                    driver_atual = None
                    conta_atual = None

            # Rotaciona para a próxima conta
            conta = HUMBLE_ACCOUNTS[indice_conta_atual]
            indice_conta_atual = (indice_conta_atual + 1) % total_contas
            contas_tentadas_consecutivas += 1

            if contas_tentadas_consecutivas > total_contas:
                _log(f"ℹ Todas as {total_contas} contas foram tentadas para a cena {idx_prompt}.")
                if ultimo_erro:
                    raise HumbleFlowError(
                        f"Não foi possível gerar a cena {idx_prompt}/{len(prompts)} "
                        f"em nenhuma conta. Último erro: {ultimo_erro}"
                    )
                raise HumbleFlowError(
                    f"Não foi possível gerar a cena {idx_prompt}/{len(prompts)} "
                    f"em nenhuma conta."
                )

            try:
                driver_atual = _abrir_conta(conta)
                conta_atual = conta

                _log(f"[CONTA #{conta_atual['indice']}] Gerando a cena {idx_prompt}...")
                arquivo = gerar_video_humble(driver_atual, prompt)

                if arquivo:
                    arquivos_baixados.append(arquivo)
                    _log(f"✔ Cena {idx_prompt} baixada: {arquivo.name}")
                    gerou = True
                    contas_tentadas_consecutivas = 0
                else:
                    _log(f"⚠ Conta #{conta_atual['indice']} não retornou arquivo. Próxima conta...")
                    _fechar_driver(driver_atual)
                    driver_atual = None
                    conta_atual = None

            except Exception as e:
                ultimo_erro = e
                _log(f"❌ Conta #{conta['indice']} não conseguiu gerar a cena {idx_prompt}: {e}")
                _fechar_driver(driver_atual)
                driver_atual = None
                conta_atual = None

        _log(f"✔ Vídeo {idx_prompt}/{len(prompts)} gerado com sucesso.")

    _fechar_driver(driver_atual)

    if not arquivos_baixados and ultimo_erro:
        _log(f"❌ Nenhum vídeo gerado. Último erro: {ultimo_erro}")

    _log(f"✔ {len(arquivos_baixados)}/{len(prompts)} cenas geradas com sucesso.")
    return arquivos_baixados