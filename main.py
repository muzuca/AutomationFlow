# arquivo: main.py
# descricao: Orquestrador principal do pipeline de conteúdo orgânico.
# Fluxo: Menu → Roteiro (Gemini WEB) → Geração de Cenas (Flow Web) → Concatenação (FFmpeg)
# Estratégia: Abre Gemini 1 vez, treina, gera TODOS os roteiros na mesma sessão,
# depois gera cenas no Flow.
# Arquitetura alinhada com AutomationFlowAnuncios (integrations/ + config.py + headless).

from __future__ import annotations

import os
import sys
import time
import signal
import random
import traceback
import threading
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Garante que a raiz do projeto está no sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import get_settings, Settings, GoogleAccount
from content.menu import exibir_menu
from content import personas


# ── PID Management (centralizado em integrations/pid_manager.py) ─────────────
from integrations import pid_manager

_shutdown_event = threading.Event()

# Instala handlers de Ctrl+C / atexit
pid_manager.instalar_handlers()

# Alias para compatibilidade
def registrar_chrome_pid(pid: int):
    pid_manager.registrar(pid)

def _matar_processos_chrome():
    pid_manager.matar_todos(motivo="pipeline_shutdown")


# ── Logging ──────────────────────────────────────────────────────────────────
def _log(msg: str, prefixo: str = "MAIN"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}][{prefixo}] {msg}")


# ── Sessão Gemini via Browser ────────────────────────────────────────────────
def _criar_sessao_gemini(settings: Settings, account: GoogleAccount):
    """
    Abre browser → login Google → abre Gemini → treina o chat.
    Retorna (driver, gemini_bot, fn_gerar_texto).
    
    fn_gerar_texto(mensagem_usuario, instrucao_sistema) -> str
    Essa função envia o prompt no chat do Gemini e retorna o texto extraído.
    """
    from integrations.browser import create_driver, close_driver
    from integrations.google_login import login_google
    from integrations.gemini import GeminiAnunciosViaFlow
    
    _log(f"Criando sessao Gemini com {account.email[:20]}...", prefixo="GEMINI")
    
    driver = create_driver(
        settings=settings,
        email_perfil=account.email,
        thread_id=0,
    )
    
    login_google(
        driver=driver,
        settings=settings,
        account=account,
    )
    
    gemini = GeminiAnunciosViaFlow(
        driver=driver,
        url_gemini=settings.gemini_url,
        thread_id=0,
    )
    
    gemini.abrir_gemini()
    _log("Gemini aberto com sucesso!", prefixo="GEMINI")
    
    def fn_gerar_texto(mensagem_usuario: str, instrucao_sistema: str) -> str:
        """Envia prompt no Gemini Web e extrai resposta."""
        # Abre novo chat para cada roteiro (evita poluição de contexto)
        gemini.abrir_novo_chat_limpo()
        
        # Combina instrução de sistema + mensagem do usuário em um único prompt
        prompt_completo = (
            f"{instrucao_sistema}\n\n"
            f"---\n\n"
            f"{mensagem_usuario}"
        )
        
        # Envia via browser e aguarda resposta (timeout 120s default)
        texto_extraido = gemini.enviar_prompt(prompt_completo, timeout=180)
        
        if not texto_extraido:
            raise RuntimeError("Gemini retornou resposta vazia via browser.")
        
        return texto_extraido
    
    return driver, gemini, fn_gerar_texto


def _matar_chrome_orfao():
    """Mata processos Chrome/ChromeDriver órfãos. Seguro para paralelismo futuro.
    
    Estratégia em 3 camadas:
      1. PIDs registrados no pid_manager (meus_pids.txt) → taskkill /T
      2. WMIC: chrome.exe com user-data-dir apontando para logs/perfis → mata por perfil
      3. Fallback: chromedriver.exe (sempre seguro matar)
      4. Cleanup: remove SingletonLock dos perfis (libera diretório)
    """
    import subprocess
    
    mortos = 0
    
    # ── 1. PIDs registrados ──────────────────────────────────────────
    try:
        from integrations import pid_manager
        pids_arquivo = pid_manager._carregar_arquivo()
        pids_memoria = set(pid_manager._pids)
        todos_pids = pids_arquivo | pids_memoria
        
        for pid in todos_pids:
            try:
                result = subprocess.run(
                    ['taskkill', '/f', '/pid', str(pid), '/T'],
                    capture_output=True, timeout=5,
                )
                if result.returncode == 0:
                    mortos += 1
            except Exception:
                pass
        
        # Limpa registros
        with pid_manager._lock:
            pid_manager._pids.clear()
        try:
            pid_manager._PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
    except Exception:
        pass
    
    # ── 2. WMIC: Chrome com perfil em logs/perfis (por caminho) ──────
    try:
        perfis_dir = str(Path("logs/perfis").resolve()).replace("\\", "\\\\")
        result = subprocess.run(
            ['wmic', 'process', 'where',
             f"name='chrome.exe' AND CommandLine LIKE '%{perfis_dir}%'",
             'get', 'ProcessId'],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.strip().split('\n'):
            pid_str = line.strip()
            if pid_str.isdigit():
                try:
                    subprocess.run(
                        ['taskkill', '/f', '/pid', pid_str],
                        capture_output=True, timeout=5,
                    )
                    mortos += 1
                except Exception:
                    pass
    except Exception:
        pass
    
    # ── 3. Chromedriver (sempre seguro — só automação usa) ───────────
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "chromedriver.exe"],
            capture_output=True, timeout=5,
        )
    except Exception:
        pass
    
    # ── 4. Remove SingletonLock dos perfis (libera diretório) ────────
    try:
        perfis_path = Path("logs/perfis")
        if perfis_path.exists():
            for pasta in perfis_path.iterdir():
                if pasta.is_dir():
                    for lock_name in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
                        lock_file = pasta / lock_name
                        if lock_file.exists():
                            try:
                                lock_file.unlink()
                            except Exception:
                                pass
    except Exception:
        pass
    
    if mortos > 0:
        _log(f"🔧 {mortos} processo(s) Chrome encerrado(s)", prefixo="CLEANUP")
    
    time.sleep(2)


# ── Reescrita de prompt rejeitado (POLICY_VIOLATION) via Gemini Browser ───────
def _reescrever_prompt_policy(driver, prompt_original: str) -> str:
    """Usa o Gemini (via browser) para reescrever um prompt rejeitado pelo Flow.
    
    Navega para o Gemini no MESMO driver, envia o pedido de reescrita,
    e retorna o prompt sanitizado. O caller deve chamar flow_bot.acessar_flow()
    depois para voltar ao workspace.
    
    Abordagem copiada do AutomationFlowAnuncios (_reescrever_prompt_cena).
    
    Returns:
        Prompt reescrito ou o original (se a reescrita falhar).
    """
    try:
        from integrations.gemini import GeminiAnunciosViaFlow
        
        gem = GeminiAnunciosViaFlow(
            driver,
            url_gemini="https://gemini.google.com/app",
            timeout=120,
            thread_id=0,
        )
        gem.abrir_gemini()
        gem.abrir_novo_chat_limpo()
        
        pedido = (
            "The prompt below was REJECTED by Google Flow (AI video generator) with a generic error. "
            "Your job is to do a MINIMAL rewrite — change ONLY the specific words or phrases that likely "
            "triggered the policy violation. Follow these rules STRICTLY:\n"
            "1) Output MUST be in the EXACT SAME LANGUAGE as the input (English). NEVER translate.\n"
            "2) Keep the EXACT same structure, format, and length.\n"
            "3) Keep the SAME visual description, camera movements, and narrative intent.\n"
            "4) ONLY remove or rephrase words that could violate content policies (e.g. body-focused "
            "descriptions, suggestive language, brand names, fortune-telling claims, "
            "references to real religions or specific spiritual practices).\n"
            "5) Keep approximately the same length. Do NOT simplify or shorten drastically.\n"
            "6) Do NOT add any explanation, commentary, or markdown formatting. "
            "Output ONLY the rewritten prompt.\n\n"
            f"REJECTED PROMPT:\n{prompt_original}"
        )
        
        resp = gem.enviar_prompt(pedido, timeout=120, aguardar_resposta=True)
        
        if resp and resp not in (
            'RECOVERY_TRIGGERED', 'TIMEOUT', 'SEM_RESPOSTA_UTIL',
            'ERRO_F5', 'SILENT_RESET',
        ):
            novo = resp.replace("```", "").strip()
            if 100 < len(novo) < len(prompt_original) * 2:
                _log(
                    f"🩺 Prompt reescrito via Gemini ({len(prompt_original)} → {len(novo)} chars)",
                    prefixo="MÉDICO"
                )
                return novo
        
        _log("⚠️ Reescrita via Gemini não retornou texto útil. Mantendo original.", prefixo="MÉDICO")
        return prompt_original
        
    except Exception as e:
        _log(f"⚠️ Reescrita falhou ({e}). Mantendo prompt original.", prefixo="MÉDICO")
        return prompt_original


# ── Geração de todas as cenas de um vídeo (1 browser, 1 sessão Flow) ─────────
def _gerar_video_completo(
    settings: Settings,
    persona_config: dict,
    roteiro: dict,
    downloads_dir: Path,
    driver_existente=None,
    flow_bot_existente=None,
    conta_existente=None,
) -> list[Path]:
    """
    Gera todas as cenas de um vídeo usando o roteiro fornecido.
    
    Se driver_existente/flow_bot_existente são fornecidos, REUTILIZA a sessão
    (apenas cria novo projeto). Caso contrário, abre browser + login + Flow.
    
    Retorna (videos_gerados, driver, flow_bot, conta) — o caller pode
    reutilizar driver/flow_bot para a próxima persona.
    """
    from integrations.browser import create_driver, close_driver
    from integrations.google_login import login_google
    from integrations.flow import GoogleFlowAutomation
    from integrations.utils import salvar_ultima_conta_env, salvar_print_debug
    
    prompts = roteiro["prompts"]
    total_cenas = len(prompts)
    contas = list(settings.accounts)
    
    # Pasta de trabalho: VIDEOS_BASE_DIR/<Personagem>/_pipeline/
    personagem = persona_config["id"]
    pasta_pipeline = Path(settings.videos_base_dir) / personagem / "_pipeline"
    pasta_pipeline.mkdir(parents=True, exist_ok=True)
    _log(f"📂 Pipeline temporário: {pasta_pipeline}", prefixo="T0")
    
    if not contas and not driver_existente:
        _log("❌ Nenhuma conta configurada no .env!")
        return []
    
    # ── RETOMADA: detecta cenas já geradas no _pipeline ──────────────
    videos_gerados: list[Path] = []
    cenas_concluidas: set[int] = set()
    
    import re as _re_resume
    for arq in sorted(pasta_pipeline.glob("cena_*_*.mp4")):
        m = _re_resume.match(r"cena_(\d+)_\d+\.mp4", arq.name)
        if m and arq.stat().st_size > 10000:  # > 10KB = arquivo válido
            idx = int(m.group(1))
            if 1 <= idx <= total_cenas:
                cenas_concluidas.add(idx)
                videos_gerados.append(arq)
    
    if cenas_concluidas:
        _log(
            f"♻️ Retomada: {len(cenas_concluidas)}/{total_cenas} cenas já existem no pipeline "
            f"({', '.join(f'cena {i}' for i in sorted(cenas_concluidas))})",
            prefixo="T0"
        )
        if len(cenas_concluidas) == total_cenas:
            _log("✅ Todas as cenas já estão prontas! Pulando geração.", prefixo="T0")
            return videos_gerados, driver_existente, flow_bot_existente, conta_existente
    
    # Se já temos sessão ativa, usa diretamente (sem login)
    _sessao_reusada = bool(driver_existente and flow_bot_existente and conta_existente)
    
    if _sessao_reusada:
        _log(f"♻️ Reaproveitando sessão Flow ({conta_existente.email[:25]}...)", prefixo="T0")
        driver = driver_existente
        flow_bot = flow_bot_existente
        conta = conta_existente
        
        # Reset do flow_bot para novo projeto (nova persona)
        flow_bot._projeto_criado = False
        flow_bot._modelo_configurado = False
        
        contas_ordenadas = [conta]
    else:
        # Prioriza a ultima conta que logou com sucesso
        ultimo_email = settings.last_account_index.lower()
        inicio = 0
        if ultimo_email:
            for i, acc in enumerate(contas):
                if acc.email.strip().lower() == ultimo_email:
                    inicio = i
                    break
        contas_ordenadas = contas[inicio:] + contas[:inicio]
        driver = None
        flow_bot = None
        conta = None
    
    for idx_conta, conta_iter in enumerate(contas_ordenadas):
        if _shutdown_event.is_set():
            break
        
        conta = conta_iter
        
        # Se a sessão já foi reusada, pula a criação do driver
        if not (_sessao_reusada and idx_conta == 0 and driver is not None):
            try:
                _log(
                    f"Abrindo sessão Flow com conta {idx_conta+1}/{len(contas_ordenadas)}: "
                    f"{conta.email[:25]}...",
                    prefixo="T0"
                )
                
                driver = create_driver(
                    settings=settings,
                    email_perfil=conta.email,
                    thread_id=0,
                )
                
                _log("Fazendo login Google...", prefixo="T0")
                login_google(
                    driver=driver,
                    settings=settings,
                    account=conta,
                )
                
                flow_bot = GoogleFlowAutomation(
                    driver=driver,
                    url_flow=settings.flow_url,
                    thread_id=0,
                )
                flow_bot.acessar_flow()
                flow_bot.verificar_creditos()
                
                salvar_ultima_conta_env(conta.email)
                
            except Exception as e:
                msg_erro = str(e)
                _log(f"Sessão falhou com {conta.email[:25]}...: {msg_erro[:80]}", prefixo="T0")
                
                if driver:
                    try: close_driver(driver)
                    except: pass
                    driver = None
                
                _matar_chrome_orfao()
                
                if idx_conta < len(contas_ordenadas) - 1:
                    _log("🔀 Tentando próxima conta...", prefixo="T0")
                    time.sleep(random.uniform(5, 10))
                    continue
                else:
                    _log("Todas as contas falharam.", prefixo="T0")
                break
        
        # ──────────────────────────────────────────────────────────
        # Loop de cenas — TODAS na mesma sessão Flow
        # ──────────────────────────────────────────────────────────
        try:
            for c_idx, prompt in enumerate(prompts, start=1):
                if _shutdown_event.is_set():
                    break
                
                if c_idx in cenas_concluidas:
                    _log(f"Cena {c_idx}/{total_cenas} — já gerada, pulando.", prefixo="T0")
                    continue
                
                _log(f"Cena {c_idx}/{total_cenas} | {conta.email[:20]}...", prefixo="T0")
                
                cena_salva = False
                _ua_consecutivos = 0
                
                for tentativa_projeto in range(1, 6):
                    if _shutdown_event.is_set():
                        break
                    
                    try:
                        flow_bot.clicar_novo_projeto()
                        
                        if not flow_bot.configurar_parametros_video():
                            flow_bot._modelo_configurado = False
                            raise Exception("Config video falhou")
                        
                        _log(
                            f"Enviando prompt ({len(prompt)} chars) "
                            f"[tentativa {tentativa_projeto}/5]...",
                            prefixo="T0"
                        )
                        resultado = flow_bot.enviar_prompt_e_aguardar(prompt)
                        
                        if resultado == "UNUSUAL_ACTIVITY":
                            _ua_consecutivos += 1
                            _log(f"Cena {c_idx} — UNUSUAL ACTIVITY #{_ua_consecutivos}", prefixo="T0")
                            
                            if _ua_consecutivos == 1:
                                _log(f"Cena {c_idx} — 🔓 DESTRAV: F5 + retry...", prefixo="T0")
                                time.sleep(random.uniform(3, 6))
                                driver.refresh()
                                time.sleep(random.uniform(3, 5))
                                flow_bot._projeto_criado = False
                                flow_bot._modelo_configurado = False
                                continue
                            elif _ua_consecutivos == 2:
                                if hasattr(flow_bot, 'modelo_veo'):
                                    if flow_bot.modelo_veo == "FAST_CREDITS":
                                        flow_bot.modelo_veo = "FAST_LOWER"
                                        _log(f"Cena {c_idx} — Fallback: Fast [Lower Priority]", prefixo="T0")
                                    elif flow_bot.modelo_veo == "FAST_LOWER":
                                        flow_bot.modelo_veo = "LITE_LOWER"
                                        _log(f"Cena {c_idx} — Fallback: Lite [Lower Priority]", prefixo="T0")
                                time.sleep(random.uniform(5, 10))
                                flow_bot.acessar_flow()
                                flow_bot._projeto_criado = False
                                flow_bot._modelo_configurado = False
                                continue
                            else:
                                _log(
                                    f"🔀 Cena {c_idx} — {_ua_consecutivos}x UNUSUAL. "
                                    f"Conta queimada! Trocando de conta...",
                                    prefixo="T0"
                                )
                                raise Exception("SWITCH_ACCOUNT_UA")
                        
                        if resultado == "POLICY_VIOLATION":
                            salvar_print_debug(driver, f"POLICY_cena{c_idx}_tent{tentativa_projeto}")
                            
                            if tentativa_projeto == 1:
                                # 1ª vez: pode ser flaky, retenta MESMO prompt
                                _log(
                                    f"🚨 Cena {c_idx} — POLICY VIOLATION (tentativa 1). "
                                    f"Retentando mesmo prompt...",
                                    prefixo="T0"
                                )
                            else:
                                # 2ª+ vez: reescreve via Gemini Browser
                                _log(
                                    f"🩺 Cena {c_idx} — POLICY VIOLATION persistente! "
                                    f"Reescrevendo prompt via Gemini Browser...",
                                    prefixo="T0"
                                )
                                prompt = _reescrever_prompt_policy(driver, prompt)
                                # Atualiza o prompt na lista para próximas tentativas
                                prompts[c_idx - 1] = prompt
                            
                            flow_bot.acessar_flow()
                            flow_bot._projeto_criado = False
                            flow_bot._modelo_configurado = False
                            continue
                        
                        if resultado != True:
                            _log(
                                f"Cena {c_idx} geração falhou (resultado={resultado}). "
                                f"Retentando em novo projeto...",
                                prefixo="T0"
                            )
                            salvar_print_debug(driver, f"FLOW_REJEITOU_cena{c_idx}_tent{tentativa_projeto}")
                            
                            # Na 3ª+ falha genérica, tenta reescrever também
                            if tentativa_projeto >= 3:
                                _log(
                                    f"🩺 Cena {c_idx} — falha persistente. "
                                    f"Reescrevendo prompt via Gemini Browser...",
                                    prefixo="T0"
                                )
                                prompt = _reescrever_prompt_policy(driver, prompt)
                                prompts[c_idx - 1] = prompt
                            
                            flow_bot.acessar_flow()
                            flow_bot._projeto_criado = False
                            flow_bot._modelo_configurado = False
                            continue
                        
                        # ── PASSO 3: Download do vídeo ──────────────────────
                        _ua_consecutivos = 0
                        nome_arquivo = f"cena_{c_idx:02d}_{int(time.time())}.mp4"
                        caminho_destino = pasta_pipeline / nome_arquivo
                        
                        ok_download = flow_bot.baixar_video_gerado(caminho_destino)
                        
                        if ok_download and caminho_destino.exists():
                            _log(f"✅ Cena {c_idx} OK: {caminho_destino.name}", prefixo="T0")
                            videos_gerados.append(caminho_destino)
                            cenas_concluidas.add(c_idx)
                            cena_salva = True
                            break
                        else:
                            _log(
                                f"❌ Download falhou cena {c_idx} (tentativa {tentativa_projeto}). "
                                f"Retentando em novo projeto...",
                                prefixo="T0"
                            )
                            try:
                                from selenium.webdriver.common.action_chains import ActionChains
                                from selenium.webdriver.common.keys import Keys
                                ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                                time.sleep(0.5)
                                ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                                time.sleep(1)
                            except:
                                pass
                            
                            flow_bot.acessar_flow()
                            flow_bot._projeto_criado = False
                            flow_bot._modelo_configurado = False
                            continue
                    
                    except Exception as e:
                        msg_exc = str(e)
                        _log(f"Erro cena {c_idx} tentativa {tentativa_projeto}: {msg_exc[:80]}", prefixo="T0")
                        
                        # ── Detecta perda de conexão ou tab crash ──
                        is_connection_dead = any(kw in msg_exc for kw in (
                            "Max retries exceeded",
                            "MaxRetryError",
                            "ConnectionRefusedError",
                            "NewConnectionError",
                            "session not created",
                            "chrome not reachable",
                            "invalid session id",
                            "tab crashed",
                        ))
                        
                        if is_connection_dead:
                            _log("🔌 Conexão/tab perdida! Recriando browser...", prefixo="T0")
                            try: close_driver(driver)
                            except: pass
                            driver = None
                            
                            _matar_chrome_orfao()
                            time.sleep(3)
                            
                            try:
                                driver = create_driver(
                                    settings=settings,
                                    email_perfil=conta.email,
                                    thread_id=0,
                                )
                                login_google(
                                    driver=driver,
                                    settings=settings,
                                    account=conta,
                                )
                                flow_bot = GoogleFlowAutomation(
                                    driver=driver,
                                    url_flow=settings.flow_url,
                                    thread_id=0,
                                )
                                flow_bot.acessar_flow()
                                flow_bot.verificar_creditos()
                                _log("✅ Browser recriado com sucesso!", prefixo="T0")
                            except Exception as e2:
                                _log(f"❌ Falha ao recriar browser: {str(e2)[:60]}", prefixo="T0")
                                break
                            continue
                        
                        # SWITCH_ACCOUNT: propaga para sair do loop de cenas
                        if "SWITCH_ACCOUNT" in msg_exc:
                            raise
                        
                        # Erro não-fatal: tenta recuperar o estado do Flow
                        try:
                            from selenium.webdriver.common.action_chains import ActionChains
                            from selenium.webdriver.common.keys import Keys
                            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                            time.sleep(0.5)
                        except:
                            pass
                        try:
                            flow_bot.acessar_flow()
                        except:
                            pass
                        flow_bot._projeto_criado = False
                        flow_bot._modelo_configurado = False
                
                if not cena_salva:
                    _log(f"❌ Falha total na cena {c_idx} após 5 tentativas", prefixo="T0")
            
            # Todas as cenas processadas — sai do loop de contas
            break
        
        except Exception as e:
            msg_erro = str(e)
            _log(f"Sessão falhou: {msg_erro[:80]}", prefixo="T0")
            
            if driver:
                try: close_driver(driver)
                except: pass
                driver = None
            
            _matar_chrome_orfao()
            
            if "SWITCH_ACCOUNT" in msg_erro:
                time.sleep(random.uniform(5, 10))
                _sessao_reusada = False
                if idx_conta < len(contas_ordenadas) - 1:
                    _log(f"🔀 Tentando próxima conta (cenas já feitas: {len(cenas_concluidas)})...", prefixo="T0")
                    continue
                else:
                    _log("Todas as contas falharam.", prefixo="T0")
            break
    
    _log(f"🎥 {len(videos_gerados)}/{total_cenas} cenas geradas com sucesso")
    # Retorna videos + sessão ativa (para reusar na próxima persona)
    return videos_gerados, driver, flow_bot, conta


# ── Processamento pós-geração (concat + move + legenda) ─────────────────────
def _processar_video_final(
    settings: Settings,
    persona_config: dict,
    videos: list[Path],
    roteiro: dict,
) -> Path | None:
    """Concatena cenas (720p copy) e faz upscale para 1080p.
    
    Trabalha dentro de _pipeline/ e move o resultado final para a pasta
    principal do personagem. Salva a legenda no legendas.txt.
    """
    from integrations.video_manager import (
        concatenar_cenas_720p,
        converter_para_1080p,
        limpar_arquivos_temporarios,
        configurar_semaforo_1080p,
    )
    from content.legendas import salvar_legenda
    
    personagem = persona_config["id"]
    tema = roteiro.get("tema_efetivo", persona_config.get("tema", "geral"))
    signo = roteiro.get("signo_efetivo", persona_config.get("signo"))
    
    # Diretórios
    destino = Path(settings.videos_base_dir) / personagem
    destino.mkdir(parents=True, exist_ok=True)
    pasta_pipeline = destino / "_pipeline"
    pasta_pipeline.mkdir(parents=True, exist_ok=True)
    
    # Configura semáforo de 1080p
    configurar_semaforo_1080p(settings.conversoes_1080p_em_paralelo)
    
    try:
        # Gera nome do arquivo final
        agora = datetime.now().strftime("%Y%m%d_%H%M%S")
        signo_str = (signo or "").replace(" ", "").replace("/", "") or "SemSigno"
        tema_str = tema.replace(" ", "_").replace("/", "")[:30]
        nome_base = f"{personagem}_{signo_str}_{tema_str}_{agora}"
        
        if len(videos) == 1:
            # Apenas 1 cena — rename direto
            video_720p = pasta_pipeline / f"{nome_base}_720p.mp4"
            videos[0].rename(video_720p)
        else:
            # Concatenar cenas em 720p (copy, sem re-encode)
            video_720p = pasta_pipeline / f"{nome_base}_720p.mp4"
            ok = concatenar_cenas_720p(videos, video_720p)
            if not ok:
                _log("❌ Falha na concatenação 720p")
                return None
            # Limpa cenas individuais
            limpar_arquivos_temporarios(videos)
        
        # Upscale para 1080p
        video_1080p = pasta_pipeline / f"{nome_base}.mp4"
        ok = converter_para_1080p(video_720p, video_1080p)
        
        if ok and video_1080p.exists():
            # Remove o 720p intermediário
            video_720p.unlink(missing_ok=True)
            
            # Move para pasta final do personagem
            import shutil
            destino_final = destino / video_1080p.name
            shutil.move(str(video_1080p), str(destino_final))
            _log(f"✅ Vídeo final: {destino_final}")
            
            # Salva legenda
            salvar_legenda(
                pasta_destino=destino,
                nome_video=destino_final.name,
                descricao=roteiro.get("descricao", ""),
                hashtags=roteiro.get("hashtags", []),
            )
            _log(f"📝 Legenda salva em legendas.txt")
            
            # Limpa pasta _pipeline (só arquivos, preserva a pasta)
            _limpar_pipeline(pasta_pipeline)
            
            return destino_final
        else:
            _log("⚠ Upscale falhou — mantendo 720p")
            import shutil
            destino_final = destino / video_720p.name
            shutil.move(str(video_720p), str(destino_final))
            
            # Salva legenda mesmo para 720p
            salvar_legenda(
                pasta_destino=destino,
                nome_video=destino_final.name,
                descricao=roteiro.get("descricao", ""),
                hashtags=roteiro.get("hashtags", []),
            )
            _log(f"📝 Legenda salva em legendas.txt")
            
            _limpar_pipeline(pasta_pipeline)
            return destino_final
    
    except Exception as e:
        _log(f"❌ Erro ao processar vídeo final: {e}")
        traceback.print_exc()
    
    return None


def _limpar_pipeline(pasta_pipeline: Path) -> None:
    """Remove todos os arquivos temporários de dentro de _pipeline/."""
    try:
        for arquivo in pasta_pipeline.glob("*"):
            if arquivo.is_file():
                arquivo.unlink(missing_ok=True)
    except Exception:
        pass


# ── Ciclo de geração para um personagem ──────────────────────────────────────
def _gerar_para_personagem(
    settings: Settings,
    persona_config: dict,
    downloads_dir: Path,
    fn_gerar_texto=None,
) -> bool:
    """Gera roteiro (via Gemini browser) + vídeo completo para um personagem."""
    persona = personas.obter(persona_config["id"])
    tema = persona_config["tema"]
    signo = persona_config.get("signo")
    n_cenas = persona_config.get("cenas_por_video", 5)
    variar_cenario = persona_config.get("variar_cenario", False)
    variar_roupa = persona_config.get("variar_roupa", False)
    
    # Mensagem central (fallback)
    mensagem_central = persona.fallback_mensagem(tema)
    
    cenario_str = "variável" if variar_cenario else "fixo"
    roupa_str = "variável" if variar_roupa else "fixa"
    _log(f"Gerando roteiro para {persona.NOME} | Tema: {tema} | Cenas: {n_cenas} | cenário {cenario_str} | roupa {roupa_str}")
    
    # Gera roteiro com retry de repetição
    max_tentativas_roteiro = 3
    roteiro = None
    
    for tentativa in range(1, max_tentativas_roteiro + 1):
        try:
            roteiro = persona.gerar_roteiro(
                tema=tema,
                mensagem_central=mensagem_central,
                signo=signo,
                n_cenas=n_cenas,
                fn_gerar_texto=fn_gerar_texto,
                variar_cenario=variar_cenario,
                variar_roupa=variar_roupa,
            )
            
            break
            
        except Exception as e:
            _log(f"Erro ao gerar roteiro (tentativa {tentativa}): {e}")
            if tentativa < max_tentativas_roteiro:
                time.sleep(3)
    
    if not roteiro:
        _log(f"❌ Não foi possível gerar roteiro para {persona.NOME}")
        return False
    
    _log(f"📝 Roteiro gerado: {roteiro.get('descricao', '')[:60]}...")
    _log(f"🏷  Hashtags: {' '.join(roteiro.get('hashtags', []))}")
    
    # Gera vídeos das cenas
    result = _gerar_video_completo(
        settings=settings,
        persona_config=persona_config,
        roteiro=roteiro,
        downloads_dir=downloads_dir,
    )
    videos, _drv, _fb, _ct = result
    # Fecha sessão (modo single-persona não reutiliza)
    if _drv:
        try:
            from integrations.browser import close_driver
            close_driver(_drv)
        except:
            pass
    
    if not videos:
        _log(f"❌ Nenhuma cena gerada para {persona.NOME}")
        return False
    
    _log(f"🎥 {len(videos)}/{len(roteiro['prompts'])} cenas geradas com sucesso")
    
    # Processa vídeo final (concat + move)
    video_final = _processar_video_final(
        settings=settings,
        persona_config=persona_config,
        videos=videos,
        roteiro=roteiro,
    )
    
    return video_final is not None


# ── Loop principal ───────────────────────────────────────────────────────────
def main():
    """Entry point do pipeline de conteudo organico."""
    print("=" * 60)
    print("  AUTOMACAO DE VIDEOS -- CONTEUDO ORGANICO")
    print("  Arquitetura v2.0 (Gemini Web + Flow)")
    print("=" * 60)
    
    # 1. Carregar configuracoes
    settings = get_settings()
    _log(f"Configuracoes carregadas | headless={settings.chrome_headless} | "
         f"engine={settings.browser_engine} | contas={len(settings.accounts)}")
    
    # 2. Sincronizar credenciais (se habilitado) — ANTES do guard de contas
    if settings.sync_humble:
        try:
            from acesso_humble import sincronizar_credenciais_humble
            sincronizar_credenciais_humble()
            # Recarrega .env no os.environ (as novas HUMBLE_EMAIL_* foram gravadas em disco)
            from dotenv import load_dotenv
            load_dotenv(Path(__file__).resolve().parent / ".env", override=True)
            settings = get_settings()  # Agora lê as contas novas
            _log(f"Contas apos sync: {len(settings.accounts)}")
        except Exception as e:
            _log(f"Sincronizacao de credenciais falhou: {e}")
    
    # Guard: precisa de contas
    if not settings.accounts:
        _log("FATAL: Nenhuma conta encontrada no .env!")
        _log("   Configure HUMBLE_EMAIL_1 / HUMBLE_PASSWORD_1 no arquivo .env")
        sys.exit(1)
    
    # 3. Limpar processos Chrome/ChromeDriver da execução anterior
    pid_manager.limpar_execucao_anterior()
    
    # 4. Limpeza de artefatos da execução anterior
    from integrations.limpeza import limpeza_inicio_execucao
    limpeza_inicio_execucao()
    
    # 4.1 Limpar cache de roteiros (sempre começa limpo)
    try:
        Path("logs/roteiros_cache.json").unlink(missing_ok=True)
    except Exception:
        pass
    
    # 5. Menu interativo
    config_sessao = exibir_menu(settings)
    modo = config_sessao["modo"]
    personagens = config_sessao["personagens"]
    
    # 5. Preparar diretorios
    downloads_dir = Path(settings.downloads_dir).resolve()
    downloads_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    _log(f"Downloads: {downloads_dir}")
    _log(f"Destino: {settings.videos_base_dir}")
    
    # 6. Helpers do watcher
    max_videos = settings.max_videos_por_personagem
    poll_minutos = settings.watcher_poll_minutos
    videos_base = Path(settings.videos_base_dir)
    
    def _contar_videos(persona_id: str) -> int:
        """Conta arquivos .mp4 no diretório de destino de um personagem."""
        pasta = videos_base / persona_id
        if not pasta.exists():
            return 0
        return len(list(pasta.glob("*.mp4")))
    
    def _personas_que_precisam(personas_list: list[dict]) -> list[dict]:
        """Retorna apenas as personas com menos de max_videos vídeos."""
        precisam = []
        for p in personas_list:
            n = _contar_videos(p["id"])
            if n < max_videos:
                precisam.append(p)
        return precisam
    
    # 7. Loop principal (watcher)
    ciclo = 0
    while not _shutdown_event.is_set():
        # ── Verificar quais personas precisam de vídeos ─────────────────
        personas_faltantes = _personas_que_precisam(personagens)
        
        if not personas_faltantes:
            # Todos no alvo — aguarda silenciosamente em background
            _log(f"ZzZz Todas as personas com {max_videos}+ videos. Aguardando em background...")
            
            while not _shutdown_event.is_set():
                time.sleep(30)
                # Reverifica silenciosamente
                if _personas_que_precisam(personagens):
                    break
            continue
        
        ciclo += 1
        
        # Mostra status de cada persona
        _log(f"\n{'='*60}")
        _log(f"CICLO {ciclo} — Watcher detectou {len(personas_faltantes)} persona(s) abaixo do alvo ({max_videos})")
        _log(f"{'='*60}")
        for p in personagens:
            n = _contar_videos(p["id"])
            status = "✅" if n >= max_videos else f"⚠️  faltam {max_videos - n}"
            _log(f"  {p['nome']}: {n}/{max_videos} {status}")
        
        # ── FASE 1: Gerar roteiros APENAS para personas que precisam ────
        roteiros_pendentes: list[dict] = []
        
        if not roteiros_pendentes:
            # Sem cache ou usuário recusou — gera normalmente
            _log(f"\n--- FASE 1: Geracao de Roteiros (Gemini Web) --- [{len(personas_faltantes)} persona(s)]")
        
            driver_gemini = None
            fn_gerar_texto = None
        
            # Tenta abrir sessao Gemini rotacionando pelas contas disponiveis
            from integrations.browser import close_driver
            from integrations.utils import salvar_ultima_conta_env
            
            contas_disponiveis = list(settings.accounts)
            if not contas_disponiveis:
                _log("FATAL: Nenhuma conta configurada!", prefixo="GEMINI")
                break
            
            # Prioriza última conta que funcionou
            ultimo_email = settings.last_account_index.strip().lower()
            inicio = 0
            if ultimo_email:
                for i, acc in enumerate(contas_disponiveis):
                    if acc.email.strip().lower() == ultimo_email:
                        inicio = i
                        break
            contas_ordenadas = contas_disponiveis[inicio:] + contas_disponiveis[:inicio]
            
            sessao_aberta = False
            for idx_conta, conta_tentativa in enumerate(contas_ordenadas):
                if _shutdown_event.is_set():
                    break
                
                _log(f"Tentando conta {idx_conta+1}/{len(contas_ordenadas)}: {conta_tentativa.email[:25]}...", prefixo="GEMINI")
                
                try:
                    driver_gemini, gemini_bot, fn_gerar_texto = _criar_sessao_gemini(
                        settings=settings,
                        account=conta_tentativa,
                    )
                    _log(f"Sessao Gemini aberta com {conta_tentativa.email[:25]}...")
                    sessao_aberta = True
                    salvar_ultima_conta_env(conta_tentativa.email)
                    break
                except Exception as e:
                    msg_erro = str(e)
                    _log(f"Conta falhou: {msg_erro[:80]}", prefixo="GEMINI")
                    if driver_gemini:
                        try: close_driver(driver_gemini)
                        except: pass
                        driver_gemini = None
                    
                    if "Chrome" in msg_erro or "session" in msg_erro:
                        _log("🔧 Chrome crashou. Limpando processos...", prefixo="GEMINI")
                        _matar_chrome_orfao()
                        time.sleep(5)
        
            if sessao_aberta and fn_gerar_texto:
                try:
                    for persona_config in personas_faltantes:
                        if _shutdown_event.is_set():
                            break
                        
                        persona = personas.obter(persona_config["id"])
                        tema = persona_config["tema"]
                        signo = persona_config.get("signo")
                        cenas_por_video = persona_config.get("cenas_por_video", 5)
                        variar_cenario = persona_config.get("variar_cenario", False)
                        variar_roupa = persona_config.get("variar_roupa", False)
                        mensagem_central = persona.fallback_mensagem(tema)
                        
                        _log(f"\n  Roteiro para {persona.NOME} | Tema: {tema} | Cenas: {cenas_por_video}\n")
                        
                        roteiro = None
                        for tentativa in range(1, 4):
                            try:
                                roteiro = persona.gerar_roteiro(
                                    tema=tema,
                                    mensagem_central=mensagem_central,
                                    signo=signo,
                                    n_cenas=cenas_por_video,
                                    fn_gerar_texto=fn_gerar_texto,
                                    variar_cenario=variar_cenario,
                                    variar_roupa=variar_roupa,
                                )
                                break
                            except Exception as e:
                                _log(f"  Erro ao gerar roteiro (tentativa {tentativa}): {e}")
                                if "SWITCH_ACCOUNT" in str(e):
                                    raise  # Propaga pra trocar de conta
                                if tentativa < 3:
                                    time.sleep(3)
                        
                        if roteiro:
                            
                            _log(f"  Roteiro OK: {roteiro.get('descricao', '')[:60]}...")
                            _log(f"  Hashtags: {' '.join(roteiro.get('hashtags', []))}")
                            _log(f"  Prompts de cena: {len(roteiro.get('prompts', []))}")
                            
                            roteiros_pendentes.append({
                                "persona_config": persona_config,
                                "roteiro": roteiro,
                            })
                        else:
                            _log(f"  FALHA: Nao foi possivel gerar roteiro para {persona.NOME}")
                
                except Exception as e:
                    _log(f"Erro durante geracao de roteiros: {e}")
                    if "SWITCH_ACCOUNT" in str(e):
                        _log("🔄 Browser morto — abortando roteiros restantes. Serão retentados no próximo ciclo.")
                        break  # Sai do loop de personas, driver será fechado abaixo
                    traceback.print_exc()
            
            # Fecha browser do Gemini (sempre)
            if driver_gemini:
                try:
                    close_driver(driver_gemini)
                except Exception:
                    pass
                driver_gemini = None
            _log("Sessao Gemini encerrada.")
        
        if not roteiros_pendentes:
            _log("Nenhum roteiro gerado neste ciclo. Pulando fase de videos.")
        else:
            _log(f"\n--- FASE 2: Geracao de Videos ({len(roteiros_pendentes)} roteiro(s)) ---")
        
        # Limpa legendas de vídeos que já foram removidos do diretório
        from content.legendas import limpar_legendas_orfas
        for pc_item in roteiros_pendentes:
            pasta_persona = Path(settings.videos_base_dir) / pc_item["persona_config"]["id"]
            if pasta_persona.exists():
                removidas = limpar_legendas_orfas(pasta_persona)
                if removidas > 0:
                    _log(f"🧹 {removidas} legenda(s) órfã(s) removida(s) de {pasta_persona.name}")
        
        # ══════════════════════════════════════════════════════════
        # SESSÃO ÚNICA: reutiliza o mesmo Chrome para TODAS as personas.
        # Só cria browser novo se a sessão morrer (crash/SWITCH_ACCOUNT).
        # ══════════════════════════════════════════════════════════
        _sessao_driver = None
        _sessao_flow_bot = None
        _sessao_conta = None
        
        # Cleanup preventivo de Chrome órfão antes de abrir sessão
        _matar_chrome_orfao()
        
        for idx, item in enumerate(roteiros_pendentes, 1):
            if _shutdown_event.is_set():
                break
            
            pc = item["persona_config"]
            rot = item["roteiro"]
            
            # Re-verifica se persona ainda precisa de vídeo
            n_atual = _contar_videos(pc["id"])
            if n_atual >= max_videos:
                _log(f"\n  [{idx}/{len(roteiros_pendentes)}] {pc['nome']} — já tem {n_atual}/{max_videos}, pulando.")
                continue
            
            _log(f"\n  [{idx}/{len(roteiros_pendentes)}] {pc['nome']} -- gerando {len(rot['prompts'])} cenas ({n_atual}/{max_videos} existentes)")
            
            try:
                result = _gerar_video_completo(
                    settings, pc, rot, downloads_dir,
                    driver_existente=_sessao_driver,
                    flow_bot_existente=_sessao_flow_bot,
                    conta_existente=_sessao_conta,
                )
                videos, _sessao_driver, _sessao_flow_bot, _sessao_conta = result
                
                if not videos:
                    _log(f"  Nenhuma cena gerada para {pc['nome']}")
                    continue
                
                total_cenas = len(rot["prompts"])
                n_geradas = len(videos)
                minimo = max(1, (total_cenas + 1) // 2)  # ceil(50%)
                
                _log(f"  {n_geradas}/{total_cenas} cenas geradas com sucesso")
                
                if n_geradas < minimo:
                    _log(
                        f"  ⚠️ Apenas {n_geradas}/{total_cenas} cenas — "
                        f"mínimo é {minimo}. Descartando vídeo incompleto.",
                    )
                    for v in videos:
                        try:
                            v.unlink(missing_ok=True)
                        except Exception:
                            pass
                    continue
                
                # Processa video final (concat + upscale + move)
                video_final = _processar_video_final(settings, pc, videos, rot)
                
                if video_final:
                    _log(f"  Video CONCLUIDO: {video_final}")
                    _log(f"  📊 {pc['nome']}: {_contar_videos(pc['id'])}/{max_videos} vídeos")
                else:
                    _log(f"  Processamento final falhou para {pc['nome']}")
                
            except Exception as e:
                _log(f"  Erro fatal na geracao de video: {e}")
                traceback.print_exc()
            
            # Pausa curta entre personas (mesma sessão, só novo projeto)
            if not _shutdown_event.is_set() and idx < len(roteiros_pendentes):
                pausa = random.uniform(3, 5)
                _log(f"  Pausa de {pausa:.0f}s antes do próximo personagem...")
                time.sleep(pausa)
        
        # ── Fecha sessão compartilhada após todas as personas ──
        if _sessao_driver:
            try:
                from integrations.browser import close_driver
                close_driver(_sessao_driver)
            except Exception:
                pass
            _sessao_driver = None
        _matar_chrome_orfao()
        

        
        # Modo unico: encerra apos 1 ciclo
        if modo == "unico":
            _log("Modo Unico -- ciclo concluido. Encerrando.")
            break
        
        # Modo continuo: limpeza entre ciclos + volta ao topo
        _log(f"Ciclo {ciclo} concluido.")
        from integrations.limpeza import limpeza_entre_tarefas
        limpeza_entre_tarefas()
        if not _shutdown_event.is_set():
            time.sleep(random.uniform(10, 20))
    
    _log("Limpeza final...")
    from integrations.limpeza import limpeza_total_shutdown
    limpeza_total_shutdown()
    _matar_processos_chrome()
    _log("Pipeline encerrado.")


if __name__ == "__main__":
    main()