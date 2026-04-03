# humble_orchestrator.py

import time
from datetime import datetime
from importlib import reload
from pathlib import Path

import automation_flow.core.config.settings as settings
from acesso_humble import sincronizar_credenciais_humble
from automation_flow.core.clients.humble_client import (
    criar_driver_humble,
    fluxo_completo_login_e_preparo,
    gerar_video_humble,
    HumbleFlowError,
    HumbleAccountDisabledError,
)

HUMBLE_ACCOUNTS = settings.HUMBLE_ACCOUNTS

MAX_TENTATIVAS_MESMO_FLOW = 3
ESPERA_ENTRE_TENTATIVAS_S = 5


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _log(msg: str):
    print(f"[{ts()}] {msg}")


# ============================================================================
#   CONTROLE DE CONTAS DESATIVADAS
# ============================================================================

_contas_desativadas: set[str] = set()


def _marcar_conta_desativada(email: str):
    _contas_desativadas.add(email)
    _log(f"🚫 Conta marcada como desativada e ignorada: {email}")


def _conta_esta_desativada(conta: dict) -> bool:
    return conta["email"] in _contas_desativadas


def _recarregar_contas() -> list[dict]:
    """
    Recarrega as contas Humble a partir do Google Doc e do .env.
    Usa sincronizar_credenciais_humble + reload(settings).
    """
    _log("♻ Ressincronizando credenciais Humble a partir do Google Doc...")
    try:
        sincronizar_credenciais_humble()
    except Exception as e:
        _log(f"❌ Erro ao sincronizar credenciais Humble: {e}")
        return []

    try:
        reload(settings)
    except Exception as e:
        _log(f"❌ Erro ao recarregar módulo de settings: {e}")
        return []

    novas = settings.HUMBLE_ACCOUNTS or []
    _log(f"ℹ {len(novas)} contas Humble carregadas após ressincronização.")

    HUMBLE_ACCOUNTS.clear()
    HUMBLE_ACCOUNTS.extend(novas)

    _contas_desativadas.clear()

    return novas


# ============================================================================
#   ABERTURA DE CONTA
# ============================================================================

def _abrir_conta(conta: dict):
    """
    Abre uma conta do Humble já logada e preparada no Flow.
    Retorna o driver pronto para gerar.

    Lança HumbleAccountDisabledError se a conta estiver desativada/bloqueada.
    Lança qualquer outra exceção se a preparação falhar por outro motivo.
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


# ============================================================================
#   GERAÇÃO COM RETRY NA MESMA SESSÃO
# ============================================================================

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
            arquivo = gerar_video_humble(
                driver,
                prompt,
            )

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

        except HumbleAccountDisabledError:
            raise

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


# ============================================================================
#   MAIN
# ============================================================================

def main(prompts: list[str]) -> list[Path]:
    """
    Ponto de entrada do Humble.

    Regras:
    - processa uma cena por vez;
    - mantém uma sessão/conta atual aberta;
    - para cada cena:
        - tenta até 3 vezes no MESMO Flow da sessão atual;
        - se mesmo assim falhar, fecha essa sessão e rotaciona para a próxima conta;
    - contas marcadas como desativadas (HumbleAccountDisabledError) são puladas
      permanentemente durante toda a execução do lote;
    - só passa para a próxima cena depois que a atual der certo.
    """
    print("=" * 55)
    print("  AUTOMAÇÃO HUMBLE → FLOW WEB")
    print("=" * 55)

    if not HUMBLE_ACCOUNTS:
        raise ValueError(
            "Nenhuma conta HUMBLE_EMAIL_N / HUMBLE_PASSWORD_N encontrada no .env"
        )

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
            # ------------------------------------------------------------------
            # 1) Tenta na conta/sessão já aberta
            # ------------------------------------------------------------------
            if driver_atual is not None and conta_atual is not None:
                try:
                    arquivo = _tentar_gerar_na_mesma_sessao(
                        driver=driver_atual,
                        conta=conta_atual,
                        prompt=prompt,
                        idx_prompt=idx_prompt,
                    )
                except HumbleAccountDisabledError as e:
                    _log(
                        f"🚫 Conta #{conta_atual['indice']} desativada durante geração: {e}"
                    )
                    _marcar_conta_desativada(conta_atual["email"])
                    _fechar_driver(driver_atual)
                    driver_atual = None
                    conta_atual = None
                    arquivo = None

                if arquivo:
                    arquivos_baixados.append(arquivo)
                    _log(f"✔ Cena {idx_prompt} baixada: {arquivo.name}")
                    gerou = True
                    break

                if driver_atual is not None:
                    _log(
                        f"⚠ Conta #{conta_atual['indice']} falhou após "
                        f"{MAX_TENTATIVAS_MESMO_FLOW} tentativas no mesmo Flow. "
                        f"Fechando sessão e rotacionando conta..."
                    )
                    _fechar_driver(driver_atual)
                    driver_atual = None
                    conta_atual = None

            # ------------------------------------------------------------------
            # 2) Verifica se ainda há contas disponíveis para esta cena
            # ------------------------------------------------------------------
            contas_ativas = [
                c for c in HUMBLE_ACCOUNTS if not _conta_esta_desativada(c)
            ]

            if contas_tentadas_nesta_cena >= len(contas_ativas) and contas_ativas:
                _log(
                    f"ℹ Todas as contas ativas ({len(contas_ativas)}) foram "
                    f"tentadas para a cena {idx_prompt}. Tentando ressincronizar "
                    f"credenciais Humble e recomeçar rotação de contas..."
                )

                novas_contas = _recarregar_contas()
                if not novas_contas:
                    msg = (
                        f"Não foi possível gerar a cena {idx_prompt}/{len(prompts)} "
                        f"em nenhuma conta disponível, mesmo após ressincronizar."
                    )
                    if ultimo_erro:
                        msg += f" Último erro: {ultimo_erro}"
                    raise HumbleFlowError(msg)

                total_contas = len(HUMBLE_ACCOUNTS)
                indice_conta_atual = 0
                contas_tentadas_nesta_cena = 0

                contas_ativas = [
                    c for c in HUMBLE_ACCOUNTS if not _conta_esta_desativada(c)
                ]

                if not contas_ativas:
                    msg = (
                        f"Não foi possível gerar a cena {idx_prompt}/{len(prompts)} "
                        f"pois todas as contas estão desativadas após ressincronizar."
                    )
                    raise HumbleFlowError(msg)

            # ------------------------------------------------------------------
            # 3) Abre próxima conta disponível
            # ------------------------------------------------------------------
            tentativas_rotacao = 0
            while tentativas_rotacao < total_contas:
                candidata = HUMBLE_ACCOUNTS[indice_conta_atual]
                indice_conta_atual = (indice_conta_atual + 1) % total_contas
                tentativas_rotacao += 1
                if not _conta_esta_desativada(candidata):
                    break
            else:
                raise HumbleFlowError(
                    "Todas as contas estão desativadas. Impossível continuar."
                )

            conta = candidata
            contas_tentadas_nesta_cena += 1

            try:
                driver_atual = _abrir_conta(conta)
                conta_atual = conta
            except HumbleAccountDisabledError as e:
                _log(
                    f"🚫 Conta #{conta['indice']} desativada durante abertura: {e}"
                )
                _marcar_conta_desativada(conta["email"])
                _fechar_driver(driver_atual)
                driver_atual = None
                conta_atual = None
                ultimo_erro = e
                continue
            except Exception as e:
                ultimo_erro = e
                _log(
                    f"❌ Conta #{conta['indice']} não conseguiu preparar o Flow: {e}"
                )
                _fechar_driver(driver_atual)
                driver_atual = None
                conta_atual = None
                continue

            # ------------------------------------------------------------------
            # 4) Tenta gerar na conta recém-aberta
            # ------------------------------------------------------------------
            try:
                arquivo = _tentar_gerar_na_mesma_sessao(
                    driver=driver_atual,
                    conta=conta_atual,
                    prompt=prompt,
                    idx_prompt=idx_prompt,
                )
            except HumbleAccountDisabledError as e:
                _log(
                    f"🚫 Conta #{conta_atual['indice']} desativada durante geração: {e}"
                )
                _marcar_conta_desativada(conta_atual["email"])
                _fechar_driver(driver_atual)
                driver_atual = None
                conta_atual = None
                arquivo = None

            if arquivo:
                arquivos_baixados.append(arquivo)
                _log(f"✔ Cena {idx_prompt} baixada: {arquivo.name}")
                gerou = True
                break

            _log(
                f"⚠ Conta #{conta_atual['indice'] if conta_atual else '?'} não conseguiu "
                f"gerar a cena {idx_prompt} mesmo após {MAX_TENTATIVAS_MESMO_FLOW} tentativas. "
                f"Próxima conta..."
            )
            if driver_atual is not None:
                _fechar_driver(driver_atual)
                driver_atual = None
                conta_atual = None

        _log(f"✔ Vídeo {idx_prompt}/{len(prompts)} gerado com sucesso.")

    _fechar_driver(driver_atual)

    if not arquivos_baixados and ultimo_erro:
        _log(f"❌ Nenhum vídeo gerado. Último erro: {ultimo_erro}")

    _log(f"✔ {len(arquivos_baixados)}/{len(prompts)} cenas geradas com sucesso.")
    return arquivos_baixados