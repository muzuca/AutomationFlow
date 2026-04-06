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
    fluxo_login_simples_sem_preparo,
    gerar_video_humble,
    HumbleFlowError,
    HumbleAccountDisabledError,
    clicar_novo_projeto,
    refresh_flow,
    _wait_visible,
    abrir_chip_nano,
    configurar_nano_video_9x16_x1_fast,
)
from selenium.webdriver.common.by import By

from automation_flow.flows.anuncios.gemini_anuncios_integration import (
    GeminiAnunciosViaFlow,
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
        _log(f"⌁ Erro ao sincronizar credenciais Humble: {e}")
        return []

    try:
        reload(settings)
    except Exception as e:
        _log(f"⌁ Erro ao recarregar módulo de settings: {e}")
        return []

    novas = settings.HUMBLE_ACCOUNTS or []
    _log(f"ℹ {len(novas)} contas Humble carregadas após ressincronização.")

    HUMBLE_ACCOUNTS.clear()
    HUMBLE_ACCOUNTS.extend(novas)
    _contas_desativadas.clear()

    return novas


def _fechar_driver(driver):
    if driver is not None:
        try:
            driver.quit()
        except Exception:
            pass


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


def _abrir_conta_para_anuncios(conta: dict):
    """
    Abre a conta Humble em login simples, sem entrar em Novo projeto/Nano.
    Ideal para: Gemini primeiro, preparação do Flow depois.
    """
    idx = conta["indice"]
    email = conta["email"]
    senha = conta["senha"]

    _log(f"[CONTA #{idx}] Inicializando conta para anúncios: {email}")

    driver = criar_driver_humble()
    fluxo_login_simples_sem_preparo(driver, email, senha)

    _log(f"[CONTA #{idx}] Login simples concluído. Pronta para Gemini + Flow.")
    return driver


def _preparar_flow_para_video(driver):
    """
    Prepara o Flow para geração de vídeo depois que o Gemini já terminou.
    """
    _log("[ANUNCIOS] Voltando ao Flow e preparando Novo projeto / Nano...")

    clicar_novo_projeto(driver)
    refresh_flow(driver, "após Novo projeto")
    _wait_visible(
        driver,
        By.XPATH,
        "//button[contains(., 'Nano Banana 2') and @aria-haspopup='menu']",
        timeout=30,
        descricao="chip Nano Banana 2 após refresh",
    )
    abrir_chip_nano(driver)
    configurar_nano_video_9x16_x1_fast(driver)

    _log("[ANUNCIOS] Flow preparado para geração do vídeo.")


def _voltar_para_aba_flow(driver):
    """
    Tenta localizar e focar a aba do Flow.
    """
    _log("[ANUNCIOS] Procurando aba do Flow para retomar a geração...")
    for handle in driver.window_handles:
        driver.switch_to.window(handle)
        try:
            url = (driver.current_url or "").lower()
        except Exception:
            url = ""

        if "labs.google/fx" in url:
            _log(f"[ANUNCIOS] Aba do Flow localizada: {url}")
            return

    raise HumbleFlowError("Não encontrei a aba do Flow para continuar a geração.")


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

        except HumbleAccountDisabledError:
            raise

        except Exception as e:
            _log(
                f"⌁ Conta #{conta['indice']} falhou na cena {idx_prompt} "
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
        f"⌁ Conta #{conta['indice']} esgotou "
        f"{MAX_TENTATIVAS_MESMO_FLOW} tentativas no mesmo Flow "
        f"para a cena {idx_prompt}."
    )
    return None


# ============================================================================
#   ANÚNCIOS
# ============================================================================

def _beneficios_padrao_por_modelo(tarefa) -> list[str]:
    slug = tarefa.modelo_slug.lower()

    if slug == "lara_select":
        return [
            "100% algodão orgânico, mais conforto",
            "sem perfume e sem substâncias tóxicas",
            "proteção segura para o dia a dia",
        ]

    if slug == "ana_indica":
        return [
            "destaque visual do produto",
            "benefício principal explicado de forma simples",
            "chamada direta para compra no TikTok Shop",
        ]

    return [
        "benefício principal do produto",
        "diferencial percebido logo no primeiro uso",
        "chamada clara para compra no TikTok Shop",
    ]


def processar_tarefa_anuncio(tarefa) -> Path:
    """
    Processa uma única tarefa de anúncio:
    - abre conta Humble com login simples;
    - gera roteiro via Gemini;
    - volta ao Flow;
    - prepara Novo projeto/Nano;
    - gera vídeo e salva em tarefa.dir_concluido.
    """
    if not HUMBLE_ACCOUNTS:
        raise HumbleFlowError(
            "Nenhuma conta HUMBLE_EMAIL_N / HUMBLE_PASSWORD_N encontrada no .env"
        )

    total_contas = len(HUMBLE_ACCOUNTS)
    indice_conta_atual = 0
    ultimo_erro = None
    contas_tentadas = 0

    while True:
        contas_ativas = [c for c in HUMBLE_ACCOUNTS if not _conta_esta_desativada(c)]
        if not contas_ativas:
            novas = _recarregar_contas()
            if not novas:
                raise HumbleFlowError(
                    f"Nenhuma conta ativa disponível para processar o anúncio {tarefa.id_anuncio}."
                )
            contas_ativas = [c for c in HUMBLE_ACCOUNTS if not _conta_esta_desativada(c)]
            if not contas_ativas:
                raise HumbleFlowError(
                    f"Todas as contas continuam indisponíveis após ressincronizar para o anúncio {tarefa.id_anuncio}."
                )

        if contas_tentadas >= len(contas_ativas):
            novas = _recarregar_contas()
            if not novas:
                msg = (
                    f"Não foi possível processar o anúncio {tarefa.id_anuncio} "
                    f"em nenhuma conta disponível."
                )
                if ultimo_erro:
                    msg += f" Último erro: {ultimo_erro}"
                raise HumbleFlowError(msg)

            total_contas = len(HUMBLE_ACCOUNTS)
            indice_conta_atual = 0
            contas_tentadas = 0
            continue

        tentativas_rotacao = 0
        conta = None
        while tentativas_rotacao < total_contas:
            candidata = HUMBLE_ACCOUNTS[indice_conta_atual]
            indice_conta_atual = (indice_conta_atual + 1) % total_contas
            tentativas_rotacao += 1
            if not _conta_esta_desativada(candidata):
                conta = candidata
                break

        if conta is None:
            raise HumbleFlowError(
                f"Todas as contas estão desativadas para o anúncio {tarefa.id_anuncio}."
            )

        contas_tentadas += 1
        driver = None

        try:
            _log(f"[ANUNCIOS] Iniciando tarefa: {tarefa}")
            driver = _abrir_conta_para_anuncios(conta)

            gemini = GeminiAnunciosViaFlow(driver)
            beneficios = _beneficios_padrao_por_modelo(tarefa)

            _log(
                f"[ANUNCIOS] Gerando roteiro no Gemini para produto "
                f"'{tarefa.nome_produto}'..."
            )
            roteiro = gemini.gerar_roteiro_anuncio(
                nome_produto=tarefa.nome_produto,
                beneficios=beneficios,
                tom="feminino, empático e direto",
                duracao=25,
            )

            if not roteiro.strip():
                raise HumbleFlowError(
                    f"Gemini retornou roteiro vazio para o anúncio {tarefa.id_anuncio}."
                )

            _log(
                f"[ANUNCIOS] Roteiro gerado com {len(roteiro)} caracteres para "
                f"anúncio #{tarefa.id_anuncio}."
            )

            _voltar_para_aba_flow(driver)
            _preparar_flow_para_video(driver)

            nome_arquivo = (
                f"{tarefa.modelo_slug}_{tarefa.tipo_filmagem}_{tarefa.id_anuncio}.mp4"
            )

            _log(
                f"[ANUNCIOS] Gerando vídeo no Flow para anúncio #{tarefa.id_anuncio}..."
            )
            video = gerar_video_humble(
                driver=driver,
                prompt=roteiro,
                destino_dir=tarefa.dir_concluido,
                nome_arquivo=nome_arquivo,
            )

            _log(
                f"[ANUNCIOS] Vídeo concluído para anúncio #{tarefa.id_anuncio}: "
                f"{video}"
            )
            return video

        except HumbleAccountDisabledError as e:
            ultimo_erro = e
            if conta:
                _log(
                    f"🚫 Conta #{conta['indice']} desativada durante anúncio "
                    f"{tarefa.id_anuncio}: {e}"
                )
                _marcar_conta_desativada(conta["email"])
            if driver is not None:
                _fechar_driver(driver)
                driver = None
            continue

        except Exception as e:
            ultimo_erro = e
            _log(
                f"⌁ Falha ao processar anúncio #{tarefa.id_anuncio} "
                f"com conta #{conta['indice'] if conta else '?'}: {e}"
            )
            if driver is not None:
                _fechar_driver(driver)
                driver = None
            continue


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
        - se mesmo assim falhar, fecha SEMPRE o driver antes de rotacionar conta;
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

                _log(
                    f"⚠ Conta #{conta_atual['indice'] if conta_atual else '?'} falhou após "
                    f"{MAX_TENTATIVAS_MESMO_FLOW} tentativas no mesmo Flow. "
                    f"Fechando sessão e rotacionando conta..."
                )
                _fechar_driver(driver_atual)
                driver_atual = None
                conta_atual = None

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
                    raise HumbleFlowError(
                        f"Não foi possível gerar a cena {idx_prompt}/{len(prompts)} "
                        f"pois todas as contas estão desativadas após ressincronizar."
                    )

            tentativas_rotacao = 0
            conta = None
            while tentativas_rotacao < total_contas:
                candidata = HUMBLE_ACCOUNTS[indice_conta_atual]
                indice_conta_atual = (indice_conta_atual + 1) % total_contas
                tentativas_rotacao += 1
                if not _conta_esta_desativada(candidata):
                    conta = candidata
                    break
            else:
                raise HumbleFlowError(
                    "Todas as contas estão desativadas. Impossível continuar."
                )

            contas_tentadas_nesta_cena += 1

            try:
                driver_atual = _abrir_conta(conta)
                conta_atual = conta
            except HumbleAccountDisabledError as e:
                _log(f"🚫 Conta #{conta['indice']} desativada durante abertura: {e}")
                _marcar_conta_desativada(conta["email"])
                _fechar_driver(driver_atual)
                driver_atual = None
                conta_atual = None
                ultimo_erro = e
                continue
            except Exception as e:
                ultimo_erro = e
                _log(f"⌁ Conta #{conta['indice']} não conseguiu preparar o Flow: {e}")
                _fechar_driver(driver_atual)
                driver_atual = None
                conta_atual = None
                continue

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
            _fechar_driver(driver_atual)
            driver_atual = None
            conta_atual = None

        _log(f"✔ Vídeo {idx_prompt}/{len(prompts)} gerado com sucesso.")

    _fechar_driver(driver_atual)

    if not arquivos_baixados and ultimo_erro:
        _log(f"⌁ Nenhum vídeo gerado. Último erro: {ultimo_erro}")

    _log(f"✔ {len(arquivos_baixados)}/{len(prompts)} cenas geradas com sucesso.")
    return arquivos_baixados