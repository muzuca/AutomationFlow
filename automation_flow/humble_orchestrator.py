# humble_orchestrator.py

import time
from datetime import datetime
from pathlib import Path

from .config import HUMBLE_ACCOUNTS
from .humble_client import (
    criar_driver_humble,
    fluxo_completo_login_e_preparo,
    gerar_video_humble,
    HumbleFlowError,
)


MAX_TENTATIVAS_MESMO_FLOW = 3
ESPERA_ENTRE_TENTATIVAS_S = 5


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(msg: str):
    print(f"[{ts()}] {msg}")


def _abrir_conta(conta: dict):
    """
    Abre uma conta do Humble já logada e preparada no Flow.
    Retorna o driver pronto para gerar.

    Se a preparação falhar, a exceção sobe e a conta é descartada
    para esta cena.
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


def _tentar_gerar_na_mesma_sessao(
    driver,
    conta: dict,
    prompt: str,
    idx_prompt: int,
) -> Path | None:
    """
    Tenta gerar a mesma cena no MESMO Flow até MAX_TENTATIVAS_MESMO_FLOW vezes.
    Entre tentativas, espera alguns segundos e reenvia o prompt.
    Retorna o Path do arquivo se conseguir, ou None se esgotar as tentativas.
    """
    for tentativa in range(1, MAX_TENTATIVAS_MESMO_FLOW + 1):
        try:
            _log(
                f"[CONTA #{conta['indice']}] Tentativa "
                f"{tentativa}/{MAX_TENTATIVAS_MESMO_FLOW} da cena {idx_prompt} "
                f"no mesmo Flow..."
            )
            arquivo = gerar_video_humble(driver, prompt)

            if arquivo:
                _log(
                    f"[CONTA #{conta['indice']}] Cena {idx_prompt} concluída "
                    f"na tentativa {tentativa}."
                )
                return arquivo

            _log(
                f"⚠ Conta #{conta['indice']} não retornou arquivo na tentativa "
                f"{tentativa}/{MAX_TENTATIVAS_MESMO_FLOW}."
            )

        except Exception as e:
            _log(
                f"❌ Conta #{conta['indice']} falhou na cena {idx_prompt} "
                f"(tentativa {tentativa}/{MAX_TENTATIVAS_MESMO_FLOW}): {e}"
            )

        if tentativa < MAX_TENTATIVAS_MESMO_FLOW:
            _log(
                f"[CONTA #{conta['indice']}] Aguardando "
                f"{ESPERA_ENTRE_TENTATIVAS_S}s para ressubmeter o mesmo prompt "
                f"no mesmo Flow..."
            )
            time.sleep(ESPERA_ENTRE_TENTATIVAS_S)

    _log(
        f"❌ Conta #{conta['indice']} esgotou "
        f"{MAX_TENTATIVAS_MESMO_FLOW} tentativas no mesmo Flow "
        f"para a cena {idx_prompt}."
    )
    return None


def main(prompts: list[str]) -> list[Path]:
    """
    Ponto de entrada do Humble.

    Regras:
    - processa uma cena por vez;
    - mantém uma sessão/conta atual aberta;
    - para cada cena:
        - tenta até 3 vezes no MESMO Flow da sessão atual;
        - se mesmo assim falhar, fecha essa sessão e rotaciona para a próxima conta;
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
        contas_tentadas_nesta_cena = 0

        while not gerou:
            # 1) tenta primeiro na conta/sessão já aberta
            if driver_atual is not None and conta_atual is not None:
                arquivo = _tentar_gerar_na_mesma_sessao(
                    driver=driver_atual,
                    conta=conta_atual,
                    prompt=prompt,
                    idx_prompt=idx_prompt,
                )

                if arquivo:
                    arquivos_baixados.append(arquivo)
                    _log(f"✔ Cena {idx_prompt} baixada: {arquivo.name}")
                    gerou = True
                    break

                _log(
                    f"⚠ Conta #{conta_atual['indice']} falhou após "
                    f"{MAX_TENTATIVAS_MESMO_FLOW} tentativas no mesmo Flow. "
                    f"Fechando sessão e rotacionando conta..."
                )
                _fechar_driver(driver_atual)
                driver_atual = None
                conta_atual = None

            # 2) se não há sessão válida, abre próxima conta
            if contas_tentadas_nesta_cena >= total_contas:
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

            conta = HUMBLE_ACCOUNTS[indice_conta_atual]
            indice_conta_atual = (indice_conta_atual + 1) % total_contas
            contas_tentadas_nesta_cena += 1

            try:
                driver_atual = _abrir_conta(conta)
                conta_atual = conta
            except Exception as e:
                ultimo_erro = e
                _log(f"❌ Conta #{conta['indice']} não conseguiu preparar o Flow: {e}")
                _fechar_driver(driver_atual)
                driver_atual = None
                conta_atual = None
                continue

            arquivo = _tentar_gerar_na_mesma_sessao(
                driver=driver_atual,
                conta=conta_atual,
                prompt=prompt,
                idx_prompt=idx_prompt,
            )

            if arquivo:
                arquivos_baixados.append(arquivo)
                _log(f"✔ Cena {idx_prompt} baixada: {arquivo.name}")
                gerou = True
                break

            _log(
                f"⚠ Conta #{conta_atual['indice']} não conseguiu gerar a cena {idx_prompt} "
                f"mesmo após {MAX_TENTATIVAS_MESMO_FLOW} tentativas. Próxima conta..."
            )
            _fechar_driver(driver_atual)
            driver_atual = None
            conta_atual = None

        _log(f"✔ Vídeo {idx_prompt}/{len(prompts)} gerado com sucesso.")

    _fechar_driver(driver_atual)

    if not arquivos_baixados and ultimo_erro:
        _log(f"❌ Nenhum vídeo gerado. Último erro: {ultimo_erro}")

    _log(f"✔ {len(arquivos_baixados)}/{len(prompts)} cenas geradas com sucesso.")
    return arquivos_baixados