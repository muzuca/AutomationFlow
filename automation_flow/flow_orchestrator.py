import time
from itertools import cycle
from pathlib import Path

import pyautogui
import pygetwindow as gw

from .config import EMAIL, SENHA, DEBUG_PORT_FG, CHROMEDRIVER_PATH
from .guru_client import (
    attach_to_chrome,
    etapa1_abrir_guru,
    etapa2_login,
    etapa3_fechar_popup,
    etapa4_buscar_flow_e_abrir,
    abrir_card_pelo_indice,
    verificar_e_fechar_popup_guru,
)
from .window_utils import (
    fechar_todas_janelas_flow_ou_login,
    fechar_janela_flow,
    finalizar_flow_alt_f4,
    finalizar_guru_alt_f4,
)
from .ocr_utils import detectar_aviso_bloqueio
from .flow_ui import (
    etapa5_flow_trocar_url,
    etapa6_flow_novo_projeto,
    etapa7_flow_configurar_opcoes,
    etapa8_flow_preencher_prompt,
    etapa9_aguardar_geracao_video,
    etapa11_aguardar_percentual_sumir,
    etapa12_abrir_player_do_video,
    etapa13_aguardar_baixar_720p,
    etapa14_esperar_download_video,
    etapa15_voltar_para_lista,
    detectar_card_de_falha,
)


MAX_FALHAS_CONSECUTIVAS = 3

# Usados apenas se Gemini falhar e nenhum prompt for passado externamente
_PROMPTS_FALLBACK = [
    "Uma mulher jovem caminhando descalça na praia ao pôr do sol, cabelos ao vento, luz dourada",
    "Silhueta feminina sentada na areia olhando o horizonte do oceano ao entardecer",
    "Mulher jovem sorrindo e girando na praia com ondas suaves ao fundo, céu alaranjado",
    "Vista aérea de uma mulher deitada na areia olhando o céu, ondas chegando suavemente",
]


# ─────────────────────────────────────────────
# ETAPA 10 — Geração com retentativas
# ─────────────────────────────────────────────

def etapa10_tentar_gerar_video_com_retentativas(
    win, prompt: str, max_tentativas: int = 10, texto_ancora=None
) -> tuple[bool, str]:
    """
    Retorna (sucesso, motivo).
    motivo: 'ok' | 'falha_persistente' | 'esgotado'
    """
    falhas_consecutivas = 0

    for tentativa in range(1, max_tentativas + 1):
        print(f"\n[ETAPA 10] Tentativa de geração #{tentativa} "
              f"(falhas consecutivas: {falhas_consecutivas}/{MAX_FALHAS_CONSECUTIVAS})...")

        try:
            etapa8_flow_preencher_prompt(win, prompt, texto_ancora=texto_ancora)
        except Exception as e:
            print(f"  ⚠ Erro ao preencher prompt: {e}. Aguardando 3s...")
            time.sleep(3)
            falhas_consecutivas += 1
            if falhas_consecutivas >= MAX_FALHAS_CONSECUTIVAS:
                print(f"  ❌ {MAX_FALHAS_CONSECUTIVAS} falhas consecutivas. Card sobrecarregado.")
                return False, "falha_persistente"
            continue

        status = etapa9_aguardar_geracao_video(win)
        print(f"  ℹ etapa9 retornou '{status}'. Analisando card mais recente...")

        if detectar_card_de_falha(win):
            falhas_consecutivas += 1
            print(f"  ❌ Card de falha detectado "
                  f"({falhas_consecutivas}/{MAX_FALHAS_CONSECUTIVAS} consecutivas).")
            if falhas_consecutivas >= MAX_FALHAS_CONSECUTIVAS:
                print(f"  ❌ {MAX_FALHAS_CONSECUTIVAS} falhas consecutivas. Trocando card...")
                return False, "falha_persistente"
            print("  → Aguardando 5s antes de tentar novamente...")
            time.sleep(5)
            continue

        falhas_consecutivas = 0

        if etapa11_aguardar_percentual_sumir(win):
            print("  ✔ Percentual sumiu. Vídeo pronto.")
            return True, "ok"

        print("  ⚠ Ainda vejo percentual nos cards. Tentando novamente após 5s.")
        time.sleep(5)

    print("  ❌ Não consegui confirmar geração após todas as tentativas.")
    return False, "esgotado"


# ─────────────────────────────────────────────
# HELPERS INTERNOS
# ─────────────────────────────────────────────

def _verificar_flow_logado(win) -> bool:
    """
    Verifica se a janela do Flow abriu na tela correta (lista de projetos ou criação).
    Faz OCR procurando elementos que indicam que o Flow está logado e pronto.
    Se não encontrar nenhum indicador positivo em 25s, retorna False.
    """
    print("  → Verificando se o Flow está logado e na tela correta...")
    import pytesseract
    import pyautogui as pg
    from .config import TESSERACT_PATH

    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

    # Indicadores mais flexíveis
    indicadores_ok = [
        "novo projeto",
        "novo",
        "projeto",
        "flow",
        "projetos",
        "criar",
        "create",
    ]
    indicadores_problema = [
        "fazer login", "login", "sign in",
        "conta bloqueada", "erro", "error",
    ]

    inicio = time.time()
    ultimo_texto = ""

    while time.time() - inicio < 25:  # 25s em vez de 20
        x0, y0, w, h = win.left, win.top, win.width, win.height
        img = pg.screenshot(region=(x0, y0, w, h))
        data = pytesseract.image_to_data(
            img, lang="por+eng", output_type=pytesseract.Output.DICT
        )
        palavras = [t.strip() for t in data["text"] if t.strip()]
        texto_completo = " ".join(palavras).lower()
        ultimo_texto = texto_completo

        # Primeiro, checa problemas
        for ind in indicadores_problema:
            if ind.lower() in texto_completo:
                print(f"  ❌ Indicador de problema detectado: '{ind}'. Flow não está logado.")
                return False

        # Depois, qualquer indício de que é a tela de projetos/criação
        for ind in indicadores_ok:
            if ind.lower() in texto_completo:
                print(f"  ✔ Indicador positivo detectado: '{ind}'. Flow OK.")
                return True

        time.sleep(2)

    # Debug: mostra um trecho do último OCR para calibrar depois
    print("  ❌ Não foi possível confirmar que o Flow está logado em 25s.")
    if ultimo_texto:
        print(f"  ℹ OCR (trecho): {ultimo_texto[:200]}...")
    return False


def _abrir_flow_para_card(driver_fg, indice_card: int) -> bool:
    """Abre o Flow para um card específico via Guru. Retorna True se conseguiu."""
    fechar_todas_janelas_flow_ou_login()
    try:
        driver_fg.switch_to.window(driver_fg.window_handles[0])
    except Exception as e:
        print(f"  ⚠ Não consegui focar a aba do Guru: {e}")
    time.sleep(2)

    if indice_card == 1:
        try:
            etapa4_buscar_flow_e_abrir(driver_fg)
            return True
        except Exception as e:
            print(f"  ❌ Erro na etapa4: {e}")
            return False

    return abrir_card_pelo_indice(driver_fg, indice_card)


def _inicializar_flow(driver_fg, indice_card: int):
    """
    Abre o Flow para o card indicado, troca URL, verifica login, configura opções.
    Retorna win_flow ou None em caso de falha.
    """
    print(f"\n[INIT FLOW] Inicializando card #{indice_card}...")

    try:
        driver_fg.switch_to.window(driver_fg.window_handles[0])
        verificar_e_fechar_popup_guru(driver_fg)
    except Exception:
        pass

    if not _abrir_flow_para_card(driver_fg, indice_card):
        return None

    win_flow = None
    for tentativa in range(1, 4):
        try:
            win_flow = etapa5_flow_trocar_url()
            break
        except RuntimeError as e:
            print(f"  ⚠ Tentativa {tentativa}/3 de focar janela falhou: {e}")
            time.sleep(5)

    if win_flow is None:
        print(f"  ❌ Não consegui abrir o Flow para o card #{indice_card}.")
        try:
            pyautogui.hotkey("alt", "f4")
            time.sleep(2)
        except Exception:
            pass
        fechar_todas_janelas_flow_ou_login()
        try:
            driver_fg.switch_to.window(driver_fg.window_handles[0])
        except Exception:
            pass
        return None

    time.sleep(4)

    if not _verificar_flow_logado(win_flow):
        print(f"  ❌ Flow do card #{indice_card} não está logado/pronto. Fechando e trocando.")
        fechar_janela_flow(win_flow)
        try:
            driver_fg.switch_to.window(driver_fg.window_handles[0])
        except Exception:
            pass
        return None

    if detectar_aviso_bloqueio(win_flow):
        print("  ❌ Aviso de bloqueio neste card.")
        fechar_janela_flow(win_flow)
        return None

    if not etapa6_flow_novo_projeto(win_flow):
        print("  ❌ Falha ao clicar em '+ Novo projeto / Nano'.")
        fechar_janela_flow(win_flow)
        return None

    if not etapa7_flow_configurar_opcoes(win_flow):
        print("  ❌ Falha ao configurar opções de vídeo.")
        fechar_janela_flow(win_flow)
        return None

    print(f"  ✔ Flow do card #{indice_card} inicializado com sucesso.")
    return win_flow


def _gerar_e_baixar(win_flow, prompt: str) -> tuple[bool, object, Path | None]:
    """
    Gera o vídeo e faz download.
    Retorna (sucesso, win_flow_atual, path_arquivo).
    Se falhou: (False, None, None).
    """
    sucesso, motivo = etapa10_tentar_gerar_video_com_retentativas(win_flow, prompt)
    if not sucesso:
        print(f"  ❌ Falha na geração (motivo: {motivo}). Fechando Flow.")
        fechar_janela_flow(win_flow)
        return False, None, None

    win_player = etapa12_abrir_player_do_video(win_flow)
    ok_download, t_clique = etapa13_aguardar_baixar_720p(win_player)
    if not ok_download or t_clique is None:
        print("  ❌ Não consegui acionar download.")
        fechar_janela_flow(win_player)
        return False, None, None

    arquivo = etapa14_esperar_download_video(t_clique)
    if not arquivo:
        print("  ❌ Download não detectado.")
        fechar_janela_flow(win_player)
        return False, None, None

    if not etapa15_voltar_para_lista(win_player):
        print("  ⚠ Não consegui voltar para a lista, mas vídeo já baixado.")

    print(f"  ✅ Vídeo gerado e baixado com sucesso. Arquivo: {arquivo}")
    return True, win_flow, Path(arquivo)


def _finalizar(driver_fg):
    print("\n[FINALIZAÇÃO] Fechando Flow e Ferramentas Guru...")
    finalizar_flow_alt_f4()
    finalizar_guru_alt_f4()
    try:
        driver_fg.quit()
    except Exception:
        pass
    print("\n✅ Fim da rotina de geração em sequência.")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main(prompts: list[str] | None = None) -> list[Path]:
    """
    Ponto de entrada da automação.

    Args:
        prompts: Lista de prompts prontos para gerar os vídeos.
                 Se None, gera via Gemini usando configuração interna.
                 Se Gemini também falhar, usa prompts fallback.

    Returns:
        Lista de Paths dos arquivos .mp4 baixados (em ordem de geração).
    """
    print("=" * 55)
    print("  AUTOMAÇÃO FERRAMENTAS GURU → FLOW (VEO 3.1)")
    print("=" * 55)

    if not EMAIL or not SENHA:
        raise ValueError("FG_EMAIL e FG_SENHA devem estar definidos no arquivo .env")

    # ── Resolve os prompts ────────────────────────────────────
    if prompts is not None:
        print(f"\n[PROMPTS] {len(prompts)} prompts recebidos externamente.")
    else:
        print("\n[PROMPTS] Nenhum prompt recebido. Gerando via Gemini interno...")
        try:
            from .gemini_client import gerar_lote_prompts
            PERSONAGEM     = "uma mulher jovem e elegante, cabelos longos escuros"
            CENARIO        = "praia ao pôr do sol com ondas suaves e céu alaranjado"
            TIPOS_MENSAGEM = [
                "inspiração e leveza",
                "saudade e melancolia suave",
                "alegria e celebração",
                "reflexão e paz interior",
            ]
            prompts = gerar_lote_prompts(
                personagem=PERSONAGEM,
                cenario=CENARIO,
                tipos_mensagem=TIPOS_MENSAGEM,
            )
            print(f"  ✔ {len(prompts)} prompts gerados via Gemini interno.")
        except Exception as e:
            print(f"  ❌ Falha ao gerar prompts via Gemini: {e}")
            print("  ℹ Usando prompts fallback pré-definidos.")
            prompts = _PROMPTS_FALLBACK

    for i, p in enumerate(prompts, 1):
        print(f"  #{i}: {p[:80]}{'...' if len(p) > 80 else ''}")

    # ── Inicia automação ──────────────────────────────────────
    etapa1_abrir_guru()
    print("\n[CONEXÃO] Anexando Selenium ao Guru (porta 9222)...")
    driver_fg = attach_to_chrome(DEBUG_PORT_FG, CHROMEDRIVER_PATH)

    etapa2_login(driver_fg, EMAIL, SENHA)
    etapa3_fechar_popup(driver_fg)

    TOTAL_CARDS = 5
    rotacao_cards = cycle(range(1, TOTAL_CARDS + 1))

    card_atual        = None
    win_flow_atual    = None
    arquivos_baixados: list[Path] = []   # ← coleta os arquivos gerados

    for idx_prompt, prompt in enumerate(prompts):
        print(f"\n{'='*55}")
        print(f"  GERANDO VÍDEO #{idx_prompt + 1}/{len(prompts)}")
        print(f"  PROMPT: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        print(f"{'='*55}")

        gerou = False
        cards_tentados_consecutivos = 0

        while not gerou:
            # Tenta no card já aberto primeiro
            if win_flow_atual is not None and card_atual is not None:
                print(f"\n  → Tentando gerar no card atual #{card_atual}...")
                try:
                    driver_fg.switch_to.window(driver_fg.window_handles[0])
                    verificar_e_fechar_popup_guru(driver_fg)
                    wins = [w for w in gw.getWindowsWithTitle("labs.google/fx")
                            if "Visual Studio Code" not in w.title]
                    if wins:
                        wins[0].activate()
                        time.sleep(0.5)
                except Exception:
                    pass

                sucesso, win_flow_atual, arquivo = _gerar_e_baixar(win_flow_atual, prompt)
                if sucesso:
                    arquivos_baixados.append(arquivo)
                    gerou = True
                    cards_tentados_consecutivos = 0
                    break
                else:
                    print(f"  ⚠ Card #{card_atual} falhou. Rotacionando...")
                    win_flow_atual = None
                    card_atual     = None

            # Rotaciona para o próximo card
            proximo_card = next(rotacao_cards)
            cards_tentados_consecutivos += 1

            if cards_tentados_consecutivos > TOTAL_CARDS:
                print(f"\n  ⏳ Todos os {TOTAL_CARDS} cards tentados. Aguardando 30s...")
                time.sleep(30)
                cards_tentados_consecutivos = 0

            try:
                driver_fg.switch_to.window(driver_fg.window_handles[0])
                verificar_e_fechar_popup_guru(driver_fg)
            except Exception:
                pass

            print(f"\n  → Inicializando card #{proximo_card}...")
            win_novo = _inicializar_flow(driver_fg, proximo_card)

            if win_novo is None:
                print(f"  ⚠ Card #{proximo_card} não pôde ser inicializado. Próximo...")
                continue

            card_atual     = proximo_card
            win_flow_atual = win_novo

            sucesso, win_flow_atual, arquivo = _gerar_e_baixar(win_flow_atual, prompt)
            if sucesso:
                arquivos_baixados.append(arquivo)
                gerou = True
                cards_tentados_consecutivos = 0
            else:
                print(f"  ⚠ Card #{card_atual} falhou na geração. Próximo...")
                card_atual     = None
                win_flow_atual = None

        print(f"\n✅ Vídeo #{idx_prompt + 1} gerado com sucesso no card #{card_atual}.")

    _finalizar(driver_fg)
    return arquivos_baixados