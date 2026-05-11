# arquivo: integrations/flow.py
# descricao: Fachada de integracao com o Google Flow (Humble) para gerar videos
# a partir do roteiro de 3 cenas. Blindado com lógica nativa do humble_client.py e Retry Local.

from __future__ import annotations

import os
import re
import sys
import time
import shutil
import pyperclip

from pathlib import Path
from typing import List, Optional, Dict, Any
from integrations.utils import _log as log_base, salvar_print_debug, js_click, scroll_ao_fim, salvar_ultimo_prompt, remover_caracteres_nao_bmp
from integrations.self_healing import cacar_elemento_universal, elemento_esta_realmente_pronto, clicar_com_hunter, interagir_com_menu_complexo, limpar_memoria_chave, superar_obstaculo_desconhecido, detectar_com_hunter

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

def _log(msg: str, thread_id: int | None = None):
    log_base(msg, prefixo="FLOW-IA", thread_id=thread_id)

class GoogleFlowAutomation:
    def __init__(self, driver, url_flow: str, driver_acessibilidade=None, url_gemini_acessibilidade=None, thread_id: int = 0):
        self.driver = driver
        self.wait = WebDriverWait(driver, 30, poll_frequency=0.2)
        self.url_flow = url_flow
        
        # Salvamos os "médicos" na classe para usar no Hunter
        self.driver_acessibilidade = driver_acessibilidade
        self.url_gemini_acessibilidade = url_gemini_acessibilidade

        # --- VARIÁVEIS DE ESTADO ---
        self.ultimo_tile_id_gerado = None
        self._projeto_criado = False
        self._modelo_configurado = False
        self._imagem_upada = False
        self.momento_ultimo_submit = 0
        self.thread_id = thread_id  # 🔀 ID da thread para isolar downloads
        
        # Flags para rastrear se as fotos já estão na mesa no Modo Imagem
        self._modelo_base_upada = False
        self._uploads_apos_modelo = 0
        
        # 🍌 Modelo de imagem configurável via .env (Nano Banana Pro vs Nano Banana 2)
        self.modelo_imagem = os.getenv('MODELO_IMAGEM_FLOW', 'Nano Banana Pro').strip()
        
        # 🎬 Modelo de vídeo — hierarquia de fallback:
        # COM créditos: LITE_CREDITS (Veo 3.1 - Lite) → FAST_CREDITS (Veo 3.1 - Fast)
        # SEM créditos: FAST_LOWER (Veo 3.1 - Fast [Lower Priority]) → LITE_LOWER (Veo 3.1 - Lite [Lower Priority])
        self.modelo_veo = "FAST_LOWER"  # Default: sem créditos
        self.creditos_conta = -1  # -1 = ainda não verificado

    # --- WRAPPERS THREAD-AWARE PARA LOG E SCREENSHOT ---
    def _tlog(self, msg: str):
        """Log com thread_id automático."""
        _log(msg, thread_id=self.thread_id)

    def _debug(self, nome_fase: str):
        """Screenshot com thread_id automático (vai para logs/visao/thread_N/)."""
        salvar_print_debug(self.driver, nome_fase, thread_id=self.thread_id)

    # --- MÉTODOS NATIVOS DO HUMBLE_CLIENT ORIGINAL BLINDADO ---
    def _wait_click(self, by: By, value: str, timeout: int = 20, descricao: str = "elemento") -> WebElement:
        """Espera um elemento ficar clicável e clica, com blindagem agressiva contra StaleElementReference."""
        fim_espera = time.time() + timeout
        
        while time.time() < fim_espera:
            try:
                el = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((by, value)))
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
                time.sleep(0.2)
                try: 
                    el.click()
                except Exception: 
                    js_click(self.driver, el)
                self._tlog(f"✔ Clicado: {descricao}")
                return el
            except Exception as e:
                msg_erro = str(e).lower()
                if "stale element reference" in msg_erro or "not attached" in msg_erro or "intercepted" in msg_erro:
                    self._tlog(f"Aviso: '{descricao}' piscou/recarregou (Stale). Tentando clicar novamente...")
                    time.sleep(0.5)
                    continue
                if isinstance(e, TimeoutException):
                    if time.time() >= fim_espera:
                        raise TimeoutException(f"Timeout ao tentar clicar em: {descricao}")
                    continue
                raise e
        raise TimeoutException(f"Timeout esgotado para o elemento: {descricao}")

    def _wait_visible(self, by: By, value: str, timeout: int = 20, descricao: str = "elemento") -> WebElement:
        el = WebDriverWait(self.driver, timeout).until(
            EC.visibility_of_element_located((by, value))
        )
        self._tlog(f"✔ Visível: {descricao}")
        return el

    # --- PROGRESSO INLINE ---
    def _print_progress_inline(self, msg: str):
        tid = getattr(self, 'thread_id', None)
        prefix = f"[T{tid}] " if tid else ""
        sys.stdout.write("\r" + (prefix + msg).ljust(120))
        sys.stdout.flush()

    def _finish_progress_inline(self, msg: str = ""):
        tid = getattr(self, 'thread_id', None)
        prefix = f"[T{tid}] " if tid else ""
        if msg:
            sys.stdout.write("\r" + (prefix + msg).ljust(120) + "\n")
        else:
            sys.stdout.write("\n")
        sys.stdout.flush()

    def _fechar_modais_intrusivos(self) -> None:
        fechou_algo = False
        try:
            termos = [
                'concordo', 'agree', 'got it', 'entendi', 'i agree', 'aceitar', 
                'accept', 'enable', 'continuar', 'continue', 'agree and continue', 
                'dismiss', 'close', 'fechar', 'ok', 'comece já'
            ]
            
            # ⚡ OTIMIZADO: JS direto em vez de Selenium find_elements para evitar implicit_wait de 5s
            js_script = """
            var termos = """ + str(termos) + """;
            var clicouAlgo = false;
            var textoClicado = "";
            
            // 1. Procura botões com termos específicos
            var candidatos = document.querySelectorAll('button, span, div[role="button"]');
            for (var c of candidatos) {
                if (c.offsetParent !== null) { // visível
                    var txt = (c.innerText || '').toLowerCase().trim();
                    // Evita clicar em caixas de texto com o prompt inteiro (ex: contendo 'tiktok' que tem 'ok')
                    if (txt.length > 0 && txt.length < 40) {
                        if (termos.some(t => txt === t || txt.startsWith(t + ' ') || txt.endsWith(' ' + t) || txt.includes(' ' + t + ' '))) {
                            c.click();
                            clicouAlgo = true;
                            textoClicado = txt;
                            return {clicou: true, texto: textoClicado};
                        }
                    }
                }
            }
            
            // 2. Procura ícones de fechar em modais
            var modais = document.querySelectorAll('div[role="dialog"] button');
            for (var m of modais) {
                if (m.offsetParent !== null) {
                    var txt = (m.innerText || '').toLowerCase().trim();
                    if (txt === 'close' || txt === 'clear') {
                        m.click();
                        return {clicou: true, texto: 'ícone/fechar'};
                    }
                }
            }
            return {clicou: false, texto: ''};
            """
            
            resultado = self.driver.execute_script(js_script)
            if resultado and resultado.get('clicou'):
                texto_limpo = str(resultado.get('texto', '')).replace('\n', ' ').replace('\r', ' ').strip()
                self._tlog(f"Modal detectado ({texto_limpo}). Fechando automaticamente...")
                time.sleep(1.0)
                fechou_algo = True
                
            if not fechou_algo:
                # Checa overlays rapidamente via JS
                tem_overlay = self.driver.execute_script("""
                    var overlays = document.querySelectorAll('div.overlay, div[role="dialog"], mat-dialog-container');
                    for (var o of overlays) {
                        if (o.offsetParent !== null) return true;
                    }
                    return false;
                """)
                if tem_overlay:
                    self._tlog("Tela de bloqueio (overlay/dialog) ativa. Forçando ESC duplo.")
                    ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                    time.sleep(0.5)
                    ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                    time.sleep(0.5)
        except Exception:
            pass
        
        # 🧠 FALLBACK INTELIGENTE: Só pede ajuda à IA se REALMENTE tem um overlay/dialog VISÍVEL
        if not fechou_algo:
            try:
                tem_bloqueio_real = self.driver.execute_script("""
                    var overlays = document.querySelectorAll('div.overlay, div[role="dialog"], mat-dialog-container, div.modal');
                    for (var o of overlays) {
                        if (o.offsetParent !== null) return true;
                    }
                    return false;
                """)
            except:
                tem_bloqueio_real = False
            
            if tem_bloqueio_real:
                try:
                    superar_obstaculo_desconhecido(
                        driver=self.driver,
                        driver_acessibilidade=getattr(self, 'driver_acessibilidade', None),
                        url_gemini=getattr(self, 'url_gemini_acessibilidade', None),
                        contexto="modal intrusivo ou popup bloqueando a interface do Google Flow"
                    )
                except: pass

    def acessar_flow(self) -> None:
        self._tlog(f'Acessando a ferramenta Flow: {self.url_flow}')
        if self.url_flow not in self.driver.current_url:
            self.driver.get(self.url_flow)
        
        self._debug("PAGINA_CARREGADA")

        try:
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except Exception:
            pass
        
        self._tlog('Analisando a interface para entrar no Workspace...')
        fim_verificacao = time.time() + 15
        
        # 🚨 Desliga espera implícita para não bloquear 5s por seletor
        self.driver.implicitly_wait(0)
        try:
            while time.time() < fim_verificacao:
                bloqueio_regiao = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'not available in your country')]")
                if bloqueio_regiao and any(b.is_displayed() for b in bloqueio_regiao):
                    self._tlog("🚨 BLOQUEIO FATAL: O Google Flow bloqueou o seu IP por região.")
                    raise Exception("Geo-Block: Ferramenta não disponível neste país. Ligue uma VPN (EUA).")

                botoes_novo = self.driver.find_elements(
                    By.XPATH, 
                    "//span[contains(text(), 'New project')] | "
                    "//button[contains(., 'New')] | "
                    "//button[contains(., 'Novo projeto')] | "
                    "//button[descendant::i[text()='add_2']]"
                )
                if any(b.is_displayed() for b in botoes_novo):
                    self._tlog('Interface do Flow (Workspace) carregada e pronta.')
                    return 

                botoes_create = self.driver.find_elements(
                    By.XPATH, 
                    "//span[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'create with flow')] | "
                    "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'create with flow')] | "
                    "//span[text()='Create'] | //button[contains(., 'Create')]"
                )
                clicou_create = False
                for btn in botoes_create:
                    if btn.is_displayed():
                        self._tlog('Botão "Create with Flow" detectado. Clicando...')
                        js_click(self.driver,btn)
                        clicou_create = True
                        time.sleep(3) 
                        self._debug("APOS_CLIQUE_CREATE")
                        break
                
                if clicou_create:
                    continue 

                self._fechar_modais_intrusivos()
                time.sleep(0.5)
        finally:
            self.driver.implicitly_wait(5)

        self._tlog('Aviso: O workspace pode não ter carregado totalmente no tempo limite.')

    def clicar_novo_projeto(self) -> None:
        if self._projeto_criado:
            self._tlog('Reaproveitando projeto atual (pulando criação)...')
            return

        self._tlog('Iniciando um novo projeto/limpando a tela...')
        t0 = time.time()
        self._fechar_modais_intrusivos()
        
        # 🚨 Desliga espera implícita para buscas rápidas
        self.driver.implicitly_wait(0)
        try:
            # --- BLOCO DE FUGA: Só sai do projeto se estiver DENTRO de um ---
            try:
                btns_voltar = self.driver.find_elements(By.XPATH, 
                    "//button[.//i[contains(text(), 'arrow_back')]] | //button[contains(., 'Voltar')]"
                )
                btn_visivel = next((b for b in btns_voltar if b.is_displayed()), None)
                if btn_visivel:
                    self._tlog("Seta Voltar detectada — saindo do projeto atual...")
                    js_click(self.driver, btn_visivel)
                    time.sleep(2)
            except:
                pass

            try:
                # ⚡ CAMINHO RÁPIDO: Busca direta do botão "Novo Projeto" (< 50ms)
                clicou = False
                xpaths_novo = [
                    "//button[descendant::i[text()='add_2']]",
                    "//span[contains(text(), 'New project')]/..",
                    "//button[contains(., 'Novo projeto')]",
                    "//button[contains(., 'New')]",
                ]
                for xp in xpaths_novo:
                    try:
                        btns = self.driver.find_elements(By.XPATH, xp)
                        for b in btns:
                            if b.is_displayed():
                                js_click(self.driver, b)
                                clicou = True
                                self._tlog(f"✔ Botão 'Novo Projeto' clicado (direto em {time.time()-t0:.1f}s)")
                                break
                    except:
                        pass
                    if clicou:
                        break
                
                # 🧠 FALLBACK: Hunter (sem Médico — botão simples, não precisa de IA)
                if not clicou:
                    if not clicar_com_hunter(
                        driver=self.driver,
                        chave_memoria="flow_btn_novo_projeto",
                        descricao_para_ia="Botão de criar novo projeto (New project ou ícone add_2) no Google Flow",
                        seletores_rapidos=xpaths_novo,
                        palavras_semanticas=["new project", "novo projeto", "add_2"],
                        etapa="FLOW_NAVEGACAO",
                        permitir_autocura=False,  # ⚡ Sem Médico (era True, desperdiçava ~30s)
                        timeout_busca=5.0,
                    ):
                        raise TimeoutException("Botão Novo Projeto não encontrado")
                
                # ⚡ POLL: Espera o textbox aparecer (em vez de sleep(3) cego)
                deadline_tb = time.time() + 5.0
                while time.time() < deadline_tb:
                    try:
                        tb = self.driver.find_elements(By.XPATH, 
                            "//div[@role='textbox' and @contenteditable='true'] | //textarea"
                        )
                        if tb and any(t.is_displayed() for t in tb):
                            break
                    except:
                        pass
                    time.sleep(0.3)
                
                self._fechar_modais_intrusivos()
                self._projeto_criado = True
                self._modelo_base_upada = False
                self._uploads_apos_modelo = 0
                self._tlog(f"✔ Novo projeto pronto em {time.time()-t0:.1f}s")
                self._debug("FLOW_NOVO_PROJETO_PRONTO")

            except TimeoutException:
                self._tlog('Botão "Novo projeto" não visível, forçando refresh...')
                self.driver.refresh()
                time.sleep(3)
                
                # ⚡ POLL: Aguarda a página carregar após o refresh
                deadline_tb = time.time() + 10.0
                while time.time() < deadline_tb:
                    try:
                        tb = self.driver.find_elements(By.XPATH, 
                            "//div[@role='textbox' and @contenteditable='true'] | //textarea"
                        )
                        if tb and any(t.is_displayed() for t in tb):
                            break
                    except:
                        pass
                    time.sleep(0.5)
                
                self._fechar_modais_intrusivos()
                self._projeto_criado = True
                self._modelo_base_upada = False
                self._uploads_apos_modelo = 0

        finally:
            self.driver.implicitly_wait(5)

    def verificar_creditos(self) -> int:
        """Verifica quantos créditos de IA a conta tem no Flow.
        
        Clica no botão ULTRA/perfil, lê o número de créditos, fecha o menu.
        Define self.modelo_veo baseado nos créditos:
          - >= 500 créditos → FAST_CREDITS (Veo 3.1 - Fast, com créditos)
          - < 500 créditos  → FAST_LOWER (Veo 3.1 - Fast [Lower Priority])
        
        Returns:
            Número de créditos, ou 0 se não conseguir ler.
        """
        # 🔒 Guard: se USE_CREDITS=False, pula direto pro modo grátis
        if not os.getenv('USE_CREDITS', 'true').strip().lower() in ('true', '1', 'yes'):
            self._tlog("💰 USE_CREDITS=False — pulando verificação, usando modo grátis.")
            self.creditos_conta = 0
            self.modelo_veo = "FAST_LOWER"
            return 0
        
        self._tlog("💰 Verificando créditos de IA da conta...")
        
        try:
            self.driver.implicitly_wait(3)
            
            # 1. Clica no botão do perfil/ULTRA (canto superior direito)
            btn_perfil = None
            try:
                # Tenta pelo texto "ULTRA"
                btn_perfil = self.driver.find_element(
                    By.XPATH,
                    "//button[.//div[contains(text(), 'ULTRA') or contains(text(), 'Ultra')]]"
                )
            except Exception:
                try:
                    # Fallback: botão com imagem de perfil
                    btn_perfil = self.driver.find_element(
                        By.XPATH,
                        "//button[contains(@class, 'sc-9b98db5b') or .//img[contains(@alt, 'perfil') or contains(@alt, 'profile')]]"
                    )
                except Exception:
                    pass
            
            if not btn_perfil:
                self._tlog("⚠️ Botão ULTRA/perfil não encontrado. Assumindo sem créditos.")
                self.creditos_conta = 0
                return 0
            
            btn_perfil.click()
            time.sleep(2)
            
            # 2. Lê o número de créditos no menu aberto
            # Estrutura real: <a class="sc-1dfd3091-4"><img ...>19295 Créditos de IA</a>
            # IMPORTANTE: text() não funciona com conteúdo misto (img + texto), usar contains(., ...)
            creditos = 0
            try:
                self._debug("CREDITOS_MENU_ABERTO")
                
                el_creditos = None
                # Tentativa 1: Pela classe exata do elemento
                try:
                    el_creditos = self.driver.find_element(By.CSS_SELECTOR, "a.sc-1dfd3091-4")
                except Exception:
                    pass
                
                # Tentativa 2: Pelo link que contém "credits" ou "ai" na URL
                if not el_creditos:
                    try:
                        el_creditos = self.driver.find_element(
                            By.XPATH,
                            "//a[contains(@href, 'ai_credits') or contains(@href, 'ai/activity')]"
                        )
                    except Exception:
                        pass
                
                # Tentativa 3: Pelo conteúdo de texto (usa . em vez de text())
                if not el_creditos:
                    try:
                        el_creditos = self.driver.find_element(
                            By.XPATH,
                            "//a[contains(., 'ditos de IA') or contains(., 'AI Credits') or contains(., 'Credits')]"
                        )
                    except Exception:
                        pass
                
                # Tentativa 4: Pelo ícone de crédito (img com credit-token)
                if not el_creditos:
                    try:
                        el_creditos = self.driver.find_element(
                            By.XPATH,
                            "//a[.//img[contains(@src, 'credit')]]"
                        )
                    except Exception:
                        pass
                
                if el_creditos:
                    texto = el_creditos.text.strip()
                    self._tlog(f"💰 Texto bruto dos créditos: '{texto}'")
                    # Extrai número: "19295 Créditos de IA" → 19295
                    import re
                    nums = re.findall(r'\d+', texto)
                    if nums:
                        creditos = int(nums[0])
                else:
                    self._tlog("⚠️ Elemento de créditos não encontrado no menu.")
            except Exception as e:
                self._tlog(f"⚠️ Não conseguiu ler créditos: {e}")
            
            # 3. Fecha o menu (ESC ou clica fora)
            try:
                ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                time.sleep(0.3)
            except Exception:
                pass
            
            self.creditos_conta = creditos
            
            # 4. Define o modelo baseado nos créditos
            if creditos >= 500:
                self.modelo_veo = "LITE_CREDITS"
                self._tlog(f"💰 {creditos} créditos encontrados! Usando Veo 3.1 - Lite (COM créditos)")
            else:
                self.modelo_veo = "FAST_LOWER"
                self._tlog(f"💰 {creditos} créditos (insuficiente). Usando Veo 3.1 - Fast [Lower Priority]")
            
            return creditos
            
        except Exception as e:
            self._tlog(f"⚠️ Erro ao verificar créditos: {e}")
            self.creditos_conta = 0
            return 0
        finally:
            self.driver.implicitly_wait(5)

    def configurar_parametros_video(self) -> bool:
        if self._modelo_configurado:
            self._tlog('Parâmetros de vídeo já configurados neste projeto (pulando)...')
            return True

        # Determina nome do modelo para log
        _nomes_modelo = {
            "LITE_CREDITS": "Veo 3.1 - Lite (COM créditos)",
            "FAST_CREDITS": "Veo 3.1 - Fast (COM créditos)",
            "FAST_LOWER": "Veo 3.1 - Fast [Lower Priority]",
            "LITE_LOWER": "Veo 3.1 - Lite [Lower Priority]"
        }
        nome_modelo = _nomes_modelo.get(self.modelo_veo, self.modelo_veo)
        self._tlog(f'Configurando parâmetros (Vídeo > 9:16 > x1 > {nome_modelo})...')
        self._fechar_modais_intrusivos() 
        
        try:
            # _debug removido do hot path (economia ~2s por chamada)
            
            # =====================================================================
            # PASSO 1: ABRIR O CHIP DO MODELO (_wait_click primário, Hunter fallback)
            # =====================================================================
            chip_encontrado = False
            xpath_chip_video = "//button[@aria-haspopup='menu' and (contains(., 'Veo') or contains(., 'Vídeo') or contains(., 'Video'))]"
            xpath_chip_img = "//button[@aria-haspopup='menu' and (contains(., 'Banana') or contains(., 'Nano'))]"
            
            try:
                self._wait_click(By.XPATH, xpath_chip_video, timeout=5, descricao="chip do Modelo (Vídeo)")
                chip_encontrado = True
            except TimeoutException:
                try:
                    self._wait_click(By.XPATH, xpath_chip_img, timeout=5, descricao="chip do Modelo (Imagem)")
                    chip_encontrado = True
                except TimeoutException:
                    self._tlog("⚠️ _wait_click falhou. Tentando fallback Hunter...")
                    chip_encontrado = clicar_com_hunter(
                        driver=self.driver,
                        chave_memoria="flow_chip_modelo_video",
                        descricao_para_ia="Chip/botão do modelo de vídeo (Veo, Video) com aria-haspopup=menu no Google Flow",
                        seletores_rapidos=[
                            "//button[@aria-haspopup='menu' and (contains(., 'Veo') or contains(., 'Vídeo') or contains(., 'Video'))]",
                            "//button[@aria-haspopup='menu' and (contains(., 'Banana') or contains(., 'Nano'))]",
                            "//button[@aria-haspopup='menu']",
                        ],
                        palavras_semanticas=["veo", "video", "model", "banana", "nano"],
                        etapa="FLOW_CONFIG_VIDEO",
                        permitir_autocura=True,
                        driver_acessibilidade=self.driver_acessibilidade,
                        url_gemini=self.url_gemini_acessibilidade,
                        timeout_busca=8.0,
                    )
                    if not chip_encontrado:
                        # Último fallback genérico
                        botoes_menu = self.driver.find_elements(By.XPATH, "//button[@aria-haspopup='menu']")
                        if botoes_menu:
                            js_click(self.driver, botoes_menu[0])
                            chip_encontrado = True

            if chip_encontrado:
                time.sleep(0.2)

                # =============================================================
                # PASSO 2: NAVEGAR O MENU DROPDOWN (_wait_click primário)
                # =============================================================
                # Aba Vídeo
                try:
                    self._wait_click(
                        By.XPATH, 
                        "//div[@role='menu' and @data-state='open']//button[.//i[text()='videocam'] or contains(., 'Vídeo') or contains(., 'Video')]", 
                        timeout=5, 
                        descricao="Aba Vídeo"
                    )
                    time.sleep(0.2)
                except TimeoutException: pass

                # 9:16
                try:
                    self._wait_click(
                        By.XPATH, 
                        "//div[@role='menu' and @data-state='open']//button[.//i[text()='crop_9_16'] or contains(., '9:16')]", 
                        timeout=5, 
                        descricao="Opção 9:16"
                    )
                    time.sleep(0.2)
                except TimeoutException: pass

                # x1
                try:
                    self._wait_click(
                        By.XPATH, 
                        "//div[@role='menu' and @data-state='open']//button[normalize-space()='1x' or normalize-space()='x1']", 
                        timeout=5, 
                        descricao="Opção x1"
                    )
                    time.sleep(0.2)
                except TimeoutException: pass

                # 8s
                try:
                    self._wait_click(
                        By.XPATH, 
                        "//div[@role='menu' and @data-state='open']//button[normalize-space()='8s']", 
                        timeout=5, 
                        descricao="Opção 8s"
                    )
                    time.sleep(0.2)
                except TimeoutException: pass

                # Submenu Veo > Seleciona modelo baseado em self.modelo_veo
                try:
                    self._wait_click(
                        By.XPATH,
                        "//div[@role='menu' and @data-state='open']//button[contains(., 'Veo')]",
                        timeout=5,
                        descricao="Dropdown submenu Veo"
                    )
                    time.sleep(0.3)
                    
                    # Seleciona o modelo correto baseado nos créditos
                    # XPaths usam button/span que é a estrutura real do dropdown do Flow
                    modelo_selecionado = False
                    
                    if self.modelo_veo == "LITE_CREDITS":
                        # COM créditos: seleciona "Veo 3.1 - Lite" (consome créditos)
                        try:
                            self._wait_click(
                                By.XPATH,
                                "//button[.//span[text()='Veo 3.1 - Lite']]",
                                timeout=5,
                                descricao="Modelo Veo 3.1 - Lite (COM créditos)"
                            )
                            modelo_selecionado = True
                        except TimeoutException:
                            self._tlog("⚠️ Lite COM créditos não encontrado.")
                    
                    if self.modelo_veo == "FAST_CREDITS" and not modelo_selecionado:
                        # COM créditos: seleciona "Veo 3.1 - Fast" (consome créditos)
                        try:
                            self._wait_click(
                                By.XPATH,
                                "//button[.//span[text()='Veo 3.1 - Fast']]",
                                timeout=5,
                                descricao="Modelo Veo 3.1 - Fast (COM créditos)"
                            )
                            modelo_selecionado = True
                        except TimeoutException:
                            self._tlog("⚠️ Fast COM créditos não encontrado.")
                    
                    if self.modelo_veo == "LITE_LOWER" and not modelo_selecionado:
                        # SEM créditos: seleciona "Veo 3.1 - Lite [Lower Priority]"
                        try:
                            self._wait_click(
                                By.XPATH,
                                "//button[.//span[contains(text(), 'Lite') and contains(text(), 'Lower')]]",
                                timeout=5,
                                descricao="Modelo Veo 3.1 - Lite [Lower Priority]"
                            )
                            modelo_selecionado = True
                        except TimeoutException:
                            self._tlog("⚠️ Lite Lower não encontrado.")
                    
                    if not modelo_selecionado:
                        # DEFAULT FALLBACK: seleciona "Veo 3.1 - Fast [Lower Priority]"
                        try:
                            self._wait_click(
                                By.XPATH,
                                "//button[.//span[contains(text(), 'Fast') and contains(text(), 'Lower')]]",
                                timeout=5,
                                descricao="Modelo Veo 3.1 - Fast [Lower Priority]"
                            )
                        except TimeoutException: pass
                        
                except TimeoutException: pass

                ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                time.sleep(0.2)
                ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()

                # =============================================================
                # PASSO 3: VALIDAÇÃO REAL — o chip mudou para Veo?
                # =============================================================
                time.sleep(0.2)
                try:
                    chips = self.driver.find_elements(By.XPATH, "//button[@aria-haspopup='menu']")
                    modelo_atual = ""
                    for c in chips:
                        txt = (c.text or "").strip()
                        if any(k in txt.lower() for k in ["veo", "banana", "nano", "video"]):
                            modelo_atual = txt
                            break
                    
                    if "veo" in modelo_atual.lower():
                        self._tlog(f'✔ Configurações do modelo aplicadas com sucesso: {modelo_atual}')
                    elif "banana" in modelo_atual.lower() or "nano" in modelo_atual.lower():
                        self._tlog(f"⚠️ Modelo ainda é '{modelo_atual}'. Acionando Médico (self-healing)...")
                        self._debug( "CONFIG_VIDEO_ANTES_SELFHEALING")
                        
                        # 🏥 SELF-HEALING: Pede à IA para navegar o menu e selecionar Veo 3.1
                        resolveu = superar_obstaculo_desconhecido(
                            driver=self.driver,
                            driver_acessibilidade=self.driver_acessibilidade,
                            url_gemini=self.url_gemini_acessibilidade,
                            contexto=(
                                "No Google Flow, o modelo de geração está configurado como 'Nano Banana 2' (modo imagem). "
                                "Preciso mudar para modo VÍDEO. O botão do modelo está na barra inferior da tela. "
                                "Clique nele para abrir o menu dropdown, depois selecione a aba 'Vídeo', "
                                "escolha proporção 9:16, quantidade x1, e modelo 'Veo 3.1 - Fast [Lower Priority]'. "
                                "Depois feche o menu com ESC."
                            )
                        )
                        
                        if resolveu:
                            # Re-valida após self-healing
                            time.sleep(1.0)
                            try:
                                chips2 = self.driver.find_elements(By.XPATH, "//button[@aria-haspopup='menu']")
                                for c2 in chips2:
                                    txt2 = (c2.text or "").strip()
                                    if "veo" in txt2.lower():
                                        self._tlog(f'✔ Médico resolveu! Modelo agora: {txt2}')
                                        break
                                else:
                                    self._tlog("🚨 Médico tentou mas modelo não mudou. Configuração FALHOU!")
                                    self._modelo_configurado = False
                                    return False
                            except Exception:
                                self._tlog("⚠️ Não foi possível re-validar após self-healing.")
                        else:
                            self._tlog("🚨 Médico não conseguiu resolver. Configuração de vídeo FALHOU!")
                            self._debug( "CONFIG_VIDEO_FALHOU_MODELO_ERRADO")
                            self._modelo_configurado = False
                            return False
                    else:
                        self._tlog(f'Configurações aplicadas (modelo: {modelo_atual or "não identificado"}).')
                except Exception:
                    self._tlog('Configurações do modelo aplicadas com sucesso.')

            else:
                self._tlog("⚠️ Não foi possível abrir o menu. Assumindo que a UI já está configurada por reuso de projeto.")

            # _debug removido do hot path (economia ~2s por chamada)
            self._modelo_configurado = True
            return True

        except Exception as e:
            self._tlog(f'🚨 Erro fatal inesperado ao configurar modelo: {e}')
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            return False

    def configurar_parametros_imagem(self) -> bool:
        if self._modelo_configurado: return True
        
        modelo_desejado = self.modelo_imagem  # Carregado do .env
        
        if modelo_desejado.strip().lower() == "misto":
            import random
            modelo_desejado = random.choice(["Nano Banana 2", "Nano Banana Pro"])
            self._tlog(f"🎲 Modo MISTO ativado! Modelo sorteado: {modelo_desejado}")
            
        self._tlog(f'Configurando parâmetros de Imagem ({modelo_desejado} > 9:16)...')
        try:
            url_antes = self.driver.current_url
            
            # PASSO 1: Clica no chip do modelo (Banana/Nano) — _wait_click ESPERA ele ficar clicável
            chip_xpath = "//button[(contains(., 'Banana') or contains(., 'Nano')) and @aria-haspopup='menu']"
            try:
                self._wait_click(By.XPATH, chip_xpath, timeout=10, descricao="chip do Modelo")
            except TimeoutException:
                self._tlog("Aviso: Chip principal não detectado. Tentando menu genérico...")
                botoes_menu = self.driver.find_elements(By.XPATH, "//button[@aria-haspopup='menu']")
                if botoes_menu: 
                    js_click(self.driver, botoes_menu[0])
            
            time.sleep(0.2)

            # PASSO 2: Seleciona 9:16 — _wait_click ESPERA o menu abrir e o botão ficar clicável
            xpath_916 = "//div[@role='menu' and @data-state='open']//button[.//i[text()='crop_9_16'] or contains(., '9:16')]"
            try:
                self._wait_click(By.XPATH, xpath_916, timeout=10, descricao="Opção 9:16")
                self._tlog("✔ Proporção 9:16 selecionada!")
            except TimeoutException:
                self._tlog("⚠️ _wait_click falhou para 9:16. Tentando Hunter + Médico...")
                clicar_com_hunter(
                    driver=self.driver,
                    chave_memoria="flow_menu_ratio_916_img",
                    descricao_para_ia="Opção de proporção 9:16 (vertical) no menu dropdown aberto de configuração do Flow. Ícone crop_9_16 ou texto 9:16.",
                    seletores_rapidos=[
                        "//button[.//i[text()='crop_9_16'] or contains(., '9:16')]",
                        "//button[.//span[contains(text(),'9:16')]]",
                    ],
                    palavras_semanticas=["9:16", "crop_9_16", "vertical", "portrait"],
                    etapa="FLOW_CONFIG_IMG",
                    timeout_busca=5.0,
                    permitir_autocura=True,
                    driver_acessibilidade=self.driver_acessibilidade,
                    url_gemini=self.url_gemini_acessibilidade,
                )
            time.sleep(0.2)

            # PASSO 2.5: SELECIONAR O MODELO DESEJADO (via .env)
            try:
                # 1. Encontra o botão do modelo dentro do menu aberto
                btn_modelo_xpath = "//div[@role='menu' and @data-state='open']//button[contains(., 'Banana') or contains(., 'Nano')]"
                btn_modelo = self.driver.find_element(By.XPATH, btn_modelo_xpath)
                
                if modelo_desejado.lower().replace(" ", "") in btn_modelo.text.lower().replace(" ", ""):
                    self._tlog(f"✔ Modelo {modelo_desejado} já estava selecionado no menu!")
                else:
                    self._wait_click(
                        By.XPATH,
                        btn_modelo_xpath,
                        timeout=5,
                        descricao="Dropdown submenu Banana"
                    )
                    time.sleep(0.3)
                    
                    # 2. Seleciona o modelo desejado no sub-menu
                    self._wait_click(
                        By.XPATH,
                        f"//div[@role='menuitem' and contains(., '{modelo_desejado}')]",
                        timeout=5,
                        descricao=f"Modelo {modelo_desejado}"
                    )
                    self._tlog(f"✔ Modelo selecionado: {modelo_desejado}")
                    time.sleep(1.0)
            except Exception as e:
                self._tlog(f"⚠️ Erro ao verificar/selecionar modelo: {str(e)[:50]}")
            
            # 3. Fecha o popup explícito de "Aviso" (Concordo/Agree)
            concordo_clicado = False
            for _ in range(16):  # 8 segundos (16 × 0.5s)
                try:
                    # Tenta vários seletores para o botão Concordo
                    xpaths_concordo = [
                        "//button[normalize-space()='Concordo']",
                        "//button[normalize-space()='Agree']",
                        "//button[contains(translate(., 'CONCORDO', 'concordo'), 'concordo')]",
                        "//button[contains(translate(., 'AGREE', 'agree'), 'agree')]",
                        "//div[contains(@class, 'dialog') or contains(@class, 'modal')]//button[last()]",
                    ]
                    for xp in xpaths_concordo:
                        try:
                            btns = self.driver.find_elements(By.XPATH, xp)
                            for btn in btns:
                                if btn.is_displayed():
                                    self.driver.execute_script("arguments[0].click();", btn)
                                    self._tlog("✔ Botão 'Concordo' clicado com sucesso no Aviso do modelo.")
                                    concordo_clicado = True
                                    break
                        except:
                            pass
                        if concordo_clicado:
                            break
                    if concordo_clicado:
                        break
                except:
                    pass
                time.sleep(0.5)
            time.sleep(0.2)

            # PASSO 3: Quantidade x1 (opcional)
            try:
                self._wait_click(
                    By.XPATH, 
                    "//div[@role='menu' and @data-state='open']//button[normalize-space()='1x' or normalize-space()='x1']", 
                    timeout=3, 
                    descricao="Opção x1"
                )
                time.sleep(0.2)
            except TimeoutException:
                pass

            self._tlog('Configurações de IMAGEM aplicadas com sucesso.')
            self._modelo_configurado = True
            
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(0.2)
            
            # VERIFICAÇÃO: Ainda estamos no edit view?
            url_depois = self.driver.current_url
            if '/edit/' not in url_depois and '/edit/' in url_antes:
                self._tlog("🚨 ALERTA: ESC fechou o edit view! Voltando...")
                self.driver.get(url_antes)
                time.sleep(3)
                return False
            
            return True

        except Exception as e:
            self._tlog(f'🚨 Erro fatal ao configurar modelo de imagem: {e}')
            return False

    def _encontrar_input_file(self) -> WebElement:
        """Encontra o input de arquivo de forma inteligente aguardando o estado do DOM (sem sleep cego)."""
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        # input[type=file] é sempre oculto, portanto checamos presença no DOM, não visibilidade.
        try:
            self._tlog("📡 Aguardando DOM renderizar o input de upload...")
            self._debug("FLOW_ANTES_INJETAR_UPLOAD")
            input_element = WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="file"], input[accept*="image"]'))
            )
            self._tlog("✔ DOM Pronto! Input de upload capturado.")
            return input_element
        except Exception as e:
            raise Exception('Nenhum input[type=file] renderizou na interface do Flow após 5s de espera.')

    # =================================================================================
    # FUNÇÕES 100% ISOLADAS: OTIMIZADAS PARA O FLUXO DE PRODUTO + MODELO NO MODAL (IMAGE BASE)
    # =================================================================================

    def _upload_produto_isolado(self, caminho: Path) -> bool:
        """Faz o upload cravando a espera até o card cinza de porcentagem sumir.
        ⚡ OTIMIZADO: JS direto em vez de Hunter (economia de ~15s por upload).
        """
        self._tlog(f"Iniciando upload isolado de: {caminho.name}...")
        nome_limpo = caminho.stem 
        
        try:
            # 1. Injeta o arquivo no input correto (sem screenshot pré-upload)
            input_file = self._encontrar_input_file()
            self.driver.execute_script("arguments[0].style.display='block'; arguments[0].style.visibility='visible'; arguments[0].style.opacity=1;", input_file)
            input_file.send_keys(str(caminho.resolve()))
            self._debug("FLOW_DEPOIS_INJETAR_UPLOAD")
            self._tlog("Arquivo injetado. Aguardando a interface registrar o card...")
            
            # 🛡️ TRATA POPUP DE "Aviso" (Direitos Autorais) com polling robusto
            # 🚨 DESLIGA implicit wait para não travar 5s por seletor vazio
            try: self.driver.implicitly_wait(0)
            except: pass
            
            concordo_ok = False
            for _ in range(16):  # 8 segundos (16 × 0.5s)
                try:
                    # CSS direto (styled-component) + XPath por texto
                    seletores = [
                        (By.XPATH, "//button[normalize-space()='Concordo']"),
                        (By.XPATH, "//button[normalize-space()='Agree']"),
                        (By.XPATH, "//button[contains(text(), 'Concordo')]"),
                        (By.XPATH, "//button[contains(text(), 'Agree')]"),
                    ]
                    for by, sel in seletores:
                        try:
                            btns = self.driver.find_elements(by, sel)
                            for btn in btns:
                                if btn.is_displayed():
                                    self.driver.execute_script("arguments[0].click();", btn)
                                    self._tlog("🛡️ Popup de 'Aviso' aceito (Concordo clicado).")
                                    concordo_ok = True
                                    break
                        except:
                            pass
                        if concordo_ok:
                            break
                    if concordo_ok:
                        break
                except:
                    pass
                time.sleep(0.5)
            if concordo_ok:
                time.sleep(0.5)
            
            # ⚡ POLL RÁPIDO: Espera o card aparecer via JS puro (~50ms por check)
            for _ in range(15):
                try:
                    tem_tile = self.driver.execute_script("return !!document.querySelector('[data-tile-id]');")
                    if tem_tile: break
                except: pass
                time.sleep(0.2)
            
            # 🚨 RELIGA implicit wait
            try: self.driver.implicitly_wait(5)
            except: pass
            
            # =========================================================
            # ⚡ LÓGICA TURBO: JS único detecta loaders + % + erros
            # =========================================================
            self._tlog("Aguardando progresso do upload (0% a 100%)...")
            fim_loader = time.time() + 90
            ultimo_log_upload = time.time()
            while time.time() < fim_loader:
                try:
                    status = self.driver.execute_script("""
                        // 1. Checa spinners e progressbars
                        var spinners = document.querySelectorAll('[class*="spin"], [role="progressbar"]');
                        for (var s of spinners) {
                            if (s.offsetParent !== null) return 'LOADING';
                        }
                        // 2. Checa textos com % nos tiles
                        var tiles = document.querySelectorAll('[data-tile-id]');
                        for (var t of tiles) {
                            var txt = t.innerText || '';
                            if (/%/.test(txt) && /\\d/.test(txt)) return 'LOADING';
                        }
                        // 3. Checa erros no tile
                        var erros = ['Falha','Failed','Error','Erro','Viola','Violat'];
                        for (var t of tiles) {
                            var inner = t.innerText || '';
                            for (var e of erros) {
                                if (inner.indexOf(e) >= 0) return 'ERRO';
                            }
                        }
                        return 'OK';
                    """)
                    if status == 'OK': break
                    if status == 'ERRO':
                        self._tlog("❌ Falha crítica: O Google Flow rejeitou a imagem no servidor.")
                        self._debug(f"3_ERRO_SERVIDOR_UPLOAD_{nome_limpo}")
                        return False
                    # 📊 Log periódico para upload longo (a cada 15s)
                    if status == 'LOADING' and time.time() - ultimo_log_upload > 15:
                        self._tlog("⏳ Upload em andamento... (aguardando servidor)")
                        ultimo_log_upload = time.time()
                except: pass
                time.sleep(0.5)

            # Respiro mínimo pro React renderizar
            time.sleep(0.2)

            # =========================================================
            # ⚡ POLL TURBO: Busca imagem finalizada via JS puro
            # =========================================================
            self._tlog(f"Procurando card da imagem finalizada na galeria...")
            fim_busca = time.time() + 30 
            encontrou = False
            
            while time.time() < fim_busca:
                try:
                    encontrou = self.driver.execute_script("""
                        var tiles = document.querySelectorAll('[data-tile-id]');
                        if (tiles.length === 0) return false;
                        
                        var validos = 0;
                        for (var i=0; i<tiles.length; i++) {
                            var t = tiles[i];
                            var temSpinner = t.querySelector('[class*="spin"], [role="progressbar"]');
                            if (!temSpinner) {
                                var img = t.querySelector('img');
                                if (img && img.offsetParent !== null && img.naturalWidth > 0) return true;
                                validos++;
                            }
                        }
                        return validos > 0;
                    """)
                    if encontrou: break
                except: pass
                time.sleep(0.3)

            if encontrou:
                self._tlog(f"✔ Upload totalmente concluído e renderizado na tela!")
                return True
            else:
                self._tlog(f"⚠️ Timeout: Imagem não renderizou na galeria após o upload.")
                self._debug(f"3_TIMEOUT_UPLOAD_{nome_limpo}")
                return False

        except Exception as e:
            self._tlog(f"🚨 Erro crítico no upload isolado: {str(e)[:100]}")
            return False
        
    def _clicar_produto_destaque(self, nome_arquivo: str) -> bool:
        """Clica na imagem do produto (que deve ser o Índice 1 após o término do upload)."""
        self._tlog(f"Procurando imagem do produto no índice 1 (Esquerda) para destaque...")
        self._debug( "FLOW_DEST_01_BUSCANDO_GRADE")

        try:
            fim_busca = time.time() + 30
            img_destaque = None
            
            while time.time() < fim_busca:
                img_destaque = cacar_elemento_universal(
                    driver=self.driver,
                    chave_memoria="flow_imagem_esquerda",
                    descricao_para_ia="A primeira miniatura de imagem na esquerda da galeria. Retorne o seletor para a tag <img> desse card.",
                    seletores_rapidos=[
                        # Matador: Pega exatamente a primeira imagem da grade que é arquivo local (sem download)
                        "(//div[@data-tile-id and not(.//button[.//i[text()='download']])]//img)[1]",
                        "(//div[@data-tile-id]//img)[1]"
                    ],
                    palavras_semanticas=['first', 'left'],
                    permitir_autocura=False, # Não aciona IA, os xpaths acima dão conta do recado
                    driver_acessibilidade=getattr(self, 'driver_acessibilidade', None),
                    url_gemini=getattr(self, 'url_gemini_acessibilidade', None),
                    etapa="FLOW_DESTAQUE"
                )
                
                if img_destaque and img_destaque.is_displayed():
                    break
                    
                time.sleep(1)

            if not img_destaque:
                self._tlog("❌ Hunter falhou: Não foi possível localizar a imagem na esquerda.")
                return False

            js_click(self.driver, img_destaque) 
            time.sleep(0.5)
            self._debug( "FLOW_DEST_02_MODAL_ABERTO")
            self._tlog("✔ Produto base (identificado na esquerda) aberto com sucesso.")
            return True
            
        except Exception as e:
            self._tlog(f"Erro crítico ao acessar imagem na esquerda: {str(e)[:100]}")
            return False

    def _anexar_modelo_pela_lista(self, nome_modelo: str, url_ancora: str) -> bool:
        """A modelo já foi upada! Abre o +, busca na aba recentes pelo nome e valida o chip."""
        self._tlog(f"Anexando a modelo ({nome_modelo}) pelo botão + da lista de recentes...")
        nome_limpo = Path(nome_modelo).stem
        
        idx_modelo = getattr(self, '_uploads_apos_modelo', 0)
        self._tlog(f"Rastreador: A foto da modelo deve estar na posição {idx_modelo} da galeria de recentes.")

        try:
            # --- 🎯 HUNTER 1: Botão "+" (add_2) ---
            xpath_add = "//button[.//i[text()='add_2']] | //button[contains(., 'Criar')]"
            btn_add = cacar_elemento_universal(
                driver=self.driver,
                chave_memoria="flow_botao_add_secundario",
                descricao_para_ia="O botão com ícone de '+' (add_2) usado para anexar mais imagens ao lado do chip principal no Google Flow.",
                seletores_rapidos=[xpath_add],
                palavras_semanticas=['add', 'criar', 'plus'],
                permitir_autocura=True, # Aqui o menu tá fechado, a IA pode agir se precisar
                driver_acessibilidade=getattr(self, 'driver_acessibilidade', None),
                url_gemini=getattr(self, 'url_gemini_acessibilidade', None),
                etapa="FLOW_ANEXO_MODAL"
            )

            if not btn_add:
                btn_add = self._wait_click(By.XPATH, xpath_add, timeout=10, descricao="Botão + (add_2)")
            else:
                js_click(self.driver, btn_add)
                
            time.sleep(2.0)

            if self.driver.current_url != url_ancora:
                self._tlog("⚠️ O Flow perdeu o foco do produto! Restaurando URL...")
                self.driver.get(url_ancora)
                time.sleep(3.0)
                btn_add = self._wait_click(By.XPATH, xpath_add, timeout=10)
                time.sleep(1.5)

            # --- 🛡️ PADRONIZAÇÃO BLOB + NOME (Alinhado com a outra função) ---
            nome_min = nome_modelo.lower()
            limpo_min = nome_limpo.lower()
            cond_alt = f"contains(translate(@alt, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{nome_min}') or contains(translate(@alt, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{limpo_min}')"

            # --- 🎯 HUNTER 2: Foto dentro do Menu Dropdown ---
            foto_modelo = cacar_elemento_universal(
                driver=self.driver,
                chave_memoria="flow_foto_modelo_dropdown",
                descricao_para_ia=f"A miniatura da modelo '{nome_limpo}' no menu suspenso de anexos.",
                seletores_rapidos=[
                    # 1. Blindagem Absoluta: Blob (Upload Local) + Nome correto
                    f"//div[@data-state='open' or contains(@role, 'menu')]//img[contains(@src, 'blob:') and ({cond_alt})]",
                    
                    # 2. Fallback de Nome sem o Blob
                    f"//div[@data-state='open' or contains(@role, 'menu')]//img[{cond_alt}]",
                    
                    # 3. Fallback Matemático: Transforma seu index 0-based do Python em 1-based do XPath
                    f"(//div[@data-state='open' or contains(@role, 'menu')]//img[contains(@src, 'blob:')])[{idx_modelo + 1}]"
                ],
                palavras_semanticas=[limpo_min, nome_min, 'blob'],
                permitir_autocura=False, # 🚨 CRÍTICO: Se a IA abrir outra aba, o menu do Flow fecha sozinho!
                driver_acessibilidade=getattr(self, 'driver_acessibilidade', None),
                url_gemini=getattr(self, 'url_gemini_acessibilidade', None),
                etapa="FLOW_ANEXO_MODAL"
            )

            if foto_modelo:
                js_click(self.driver, foto_modelo)
                self._tlog(f"✔ Imagem da modelo ({nome_limpo}) selecionada via Hunter (Proteção Blob Ativa).")
                self._debug( "FLOW_ANEXO_CHIP_OK")
            else:
                self._tlog("⚠️ Hunter falhou. Usando fallback extremo cego...")
                xpath_fallback_extremo = "//div[@data-state='open' or contains(@role, 'menu')]//div[contains(@class, 'grid') or contains(@class, 'list')]//button//img"
                fallbacks_ext = self.driver.find_elements(By.XPATH, xpath_fallback_extremo)
                if fallbacks_ext and fallbacks_ext[0].is_displayed():
                    js_click(self.driver, fallbacks_ext[0])
                    self._tlog("⚠️ Fallback extremo clicado.")
                    self._debug( "FLOW_ANEXO_FALLBACK_EXTREMO")

            time.sleep(1.5)
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(1.0)

            # --- VALIDAÇÃO FINAL ---
            xpath_chip = "//button[.//i[text()='cancel']]"
            chips = self.driver.find_elements(By.XPATH, xpath_chip)
            if chips and any(c.is_displayed() for c in chips):
                self._tlog("✔ Confirmação: Modelo anexada perfeitamente no quadradinho (chip)!")
                self._debug( "FLOW_ANEXO_CHIP_CONFIRMADO")
                return True
            
            return False
            
        except Exception as e:
            self._tlog(f"Erro fatal ao selecionar modelo da lista: {str(e).splitlines()[0]}")
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            return False

    def _digitar_prompt_imagem(self, prompt: str) -> bool:
        """Digita o prompt na caixa de texto (sem enviar)."""
        import os
        import time
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.by import By
        
        def js_click(driver, element):
            driver.execute_script("arguments[0].click();", element)

        self._tlog("Digitando prompt na caixa...")

        prompt_linear = remover_caracteres_nao_bmp(" ".join(prompt.replace('\n', ' ').replace('\r', ' ').split()))
        
        # 🛡️ CAMADA 3: Guard de tamanho antes do send_keys
        # Um prompt de imagem do Flow tem ~300-800 chars. Se tem >2000, está corrompido.
        MAX_PROMPT_FLOW = 2000
        if len(prompt_linear) > MAX_PROMPT_FLOW:
            self._tlog(f"🚨 GUARD FLOW: Prompt com {len(prompt_linear)} chars (max {MAX_PROMPT_FLOW}). Prompt corrompido — ABORTANDO envio!")
            self._tlog(f"🚨 Primeiros 200 chars: {prompt_linear[:200]}...")
            return False
        
        try:
            from integrations.utils import salvar_ultimo_prompt
            salvar_ultimo_prompt(f"--- PROMPT ENVIADO AO FLOW (IMAGEM) ---\n{prompt_linear}")
        except: pass

        try:
            xpath_box = "//div[@role='textbox' and @contenteditable='true'] | //textarea"
            # 🛡️ HUNTER: Busca caixa de texto via cache
            box = cacar_elemento_universal(
                driver=self.driver,
                chave_memoria="flow_textarea_prompt_img",
                descricao_para_ia="Caixa de texto (textbox contenteditable) para digitar prompt de imagem no Google Flow",
                seletores_rapidos=[xpath_box],
                palavras_semanticas=[],
                permitir_autocura=False,
                etapa="FLOW_SUBMIT_IMG",
            )
            
            if not box:
                caixas = self.driver.find_elements(By.XPATH, xpath_box)
                box = next((c for c in caixas if c.is_displayed()), None)
            
            if not box:
                self._tlog("⚠️ Caixa de texto não encontrada.")
                return False
            
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'}); arguments[0].focus();", box)
            js_click(self.driver, box)
            time.sleep(0.5)
            
            # Limpa e injeta
            box.send_keys(Keys.CONTROL, "a")
            box.send_keys(Keys.BACKSPACE)
            
            is_headless = os.getenv('CHROME_HEADLESS', 'False').lower() == 'true'
            if is_headless:
                box.send_keys(prompt_linear)
                self.driver.execute_script("arguments[0].dispatchEvent(new Event('input', { bubbles: true }));", box)
            else:
                import pyperclip
                pyperclip.copy(prompt_linear)
                box.send_keys(Keys.CONTROL, 'v')

            self._debug( "FLOW_DEPOIS_COLAR_PROMPT")                    

            return True

        except Exception as e:
            self._tlog(f"Erro ao digitar prompt: {e}")
            return False

    def _submeter_prompt_imagem(self, timeout_geracao: int = 120) -> bool:
        """Clica no botão de enviar da caixa de prompt e monitora a geração."""
        import time
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        import threading
        
        # Lock global para evitar que múltiplas threads submetam ao mesmo tempo e tomem Rate Limit
        if not hasattr(self.__class__, '_submit_lock'):
            self.__class__._submit_lock = threading.Lock()
            
        def js_click(driver, element):
            driver.execute_script("arguments[0].click();", element)
            
        try:
            xpath_box = "//div[@role='textbox' and @contenteditable='true'] | //textarea"
            caixas = self.driver.find_elements(By.XPATH, xpath_box)
            box = next((c for c in caixas if c.is_displayed()), None)
            
            if not box:
                self._tlog("⚠️ Caixa de texto não encontrada para submeter.")
                return False

            self._tlog("Submetendo prompt (Fluxo isolado de Imagem)...")

            # 📸 PRINT CRÍTICO: Estado da tela ANTES do submit (modelo ainda no chip?)
            self._debug( "FLOW_ANTES_SUBMIT_ESTADO")

            time.sleep(0.5)

            # Tenta clicar o botão de enviar via Hunter
            # --- SUBMIT: Lógica FUNCIONAL do commit (find_elements direto + disabled check) ---
            xpath_submit = "//button[.//i[contains(text(), 'arrow') or contains(text(), 'send') or contains(text(), 'sparkle')]] | //button[contains(@aria-label, 'Gerar')]"
            btns = self.driver.find_elements(By.XPATH, xpath_submit)
            
            if btns and btns[-1].is_displayed():
                btn_send = btns[-1]
                
                # Aguarda o lock para não submeter simultaneamente
                with self.__class__._submit_lock:
                    self._tlog("🚦 Semáforo verde: Submetendo prompt...")
                    if btn_send.get_attribute("disabled") is not None:
                        box.send_keys(Keys.CONTROL, Keys.ENTER)
                    else:
                        try: btn_send.click()
                        except: js_click(self.driver, btn_send)
                    
                    # Pequeno delay enquanto segura o lock para evitar que a outra thread mande imediatamente
                    time.sleep(3)
            else:
                with self.__class__._submit_lock:
                    self._tlog("🚦 Semáforo verde: Submetendo prompt (via atalho)...")
                    box.send_keys(Keys.CONTROL, Keys.ENTER)
                    time.sleep(3)

            self._debug( "FLOW_APOS_SUBMIT_PROMPT")
            momento_submit = time.time()
            
            # --- MONITORAMENTO COM RADAR DE FALHA GLOBAL ---
            # ⚡ POLL: Espera o primeiro sinal de vida (tile ou stop btn) em vez de sleep(7) cego
            self._tlog(f"Monitorando geração (máx {timeout_geracao}s)...")
            for _ in range(15):  # Max 3s de espera ativa
                try:
                    indicadores = self.driver.find_elements(By.XPATH, 
                        "//button[contains(.,'Stop') or contains(.,'Parar')] | //*[contains(@class,'progress') or contains(@class,'spin')]")
                    if indicadores: break
                except: pass
                time.sleep(0.2)
            
            # Garante a contagem de tempo
            momento_submit = time.time()
            fim_espera = momento_submit + timeout_geracao

            while time.time() < fim_espera:
                # 🚀 SCRIPT RADAR AVANÇADO
                status = self.driver.execute_script("""
                    var txt = document.body.innerText.toLowerCase();
                    
                    // 1a. Verifica RATE LIMIT (precisa esperar, não desistir)
                    var rate_limits = ['solicitando gerações muito rápido', 'requesting generations too quickly',
                                       'too many requests', 'rate limit'];
                    for (var r of rate_limits) {
                        if (txt.includes(r)) return 'RATE_LIMIT';
                    }
                    
                    // 1b. Verifica falhas críticas (frases específicas para evitar falso positivo)
                    var falhas = ['unusual activity', 'policy violation', 'against our policy',
                                  'generation failed', 'could not generate', 'unable to generate',
                                  'request failed', 'something went wrong', 'we noticed unusual',
                                  'falha na geração', 'não foi possível gerar', 'atividade incomum',
                                  'violação de política', 'contra nossa política'];
                    for (var f of falhas) {
                        if (txt.includes(f)) return 'FALHA';
                    }
                    
                    // 2. Procura ativamente pelo botão de download (por texto ou ícone)
                    var btns = document.querySelectorAll('button');
                    for (var b of btns) {
                        var b_txt = b.innerText.toLowerCase();
                        if (b_txt.includes('download') || b_txt.includes('baixar') || b.innerHTML.includes('download')) {
                            return 'SUCESSO_BOTAO';
                        }
                    }
                    
                    // 3. Fallback: Se a caixa de texto secou, significa que enviou. 
                    // Se enviou e não tem mais botão de "Stop", é porque gerou.
                    var box = document.querySelector('div[role="textbox"], textarea');
                    if (box && box.innerText.trim() === '') {
                        var is_generating = false;
                        for (var b of btns) {
                            if (b.innerText.toLowerCase().includes('stop') || b.innerHTML.includes('stop')) {
                                is_generating = true;
                            }
                        }
                        if (!is_generating) {
                            return 'SUCESSO_FALLBACK';
                        }
                    }
                    
                    return 'AGUARDANDO';
                """)
                
                if status == 'RATE_LIMIT':
                    rate_limit_count = getattr(self, '_rate_limit_retries', 0) + 1
                    self._rate_limit_retries = rate_limit_count
                    self._tlog(f"⏳ RATE LIMIT detectado (tentativa {rate_limit_count}/3). Fechando popup e resubmetendo...")
                    self._debug("FLOW_RATE_LIMIT")
                    
                    if rate_limit_count > 3:
                        self._tlog("🚫 Rate limit persistente. Abortando esta geração.")
                        self._rate_limit_retries = 0
                        return False  # Sai para o loop externo criar novo projeto
                    
                    # Fecha o popup de rate limit (X ou botão dismiss)
                    try:
                        self.driver.execute_script("""
                            // Tenta fechar pelo botão X/fechar do popup
                            var allBtns = document.querySelectorAll('button, [role="button"]');
                            for (var b of allBtns) {
                                var lbl = (b.getAttribute('aria-label') || '').toLowerCase();
                                var txt = (b.innerText || '').toLowerCase();
                                if (lbl.includes('close') || lbl.includes('fechar') || lbl.includes('dismiss') ||
                                    txt.includes('fechar') || txt.includes('dismiss') ||
                                    b.innerHTML.includes('close') || b.innerHTML.includes('M19 ')) {
                                    b.click(); return 'FECHOU';
                                }
                            }
                            // Fallback: ESC
                            return 'NAO_ACHOU';
                        """)
                    except: pass
                    
                    time.sleep(10)
                    
                    # Resubmete o prompt (a imagem do produto ainda está selecionada)
                    try:
                        from selenium.webdriver.common.keys import Keys
                        box = self.driver.find_element(By.CSS_SELECTOR, 'div[role="textbox"], textarea')
                        if box:
                            box.click()
                            time.sleep(0.5)
                            
                            # Verifica se a caixa secou (Flow apagou). Se sim, digita de novo.
                            # NÃO USAR CTRL+A pois isso deleta o chip da modelo!
                            txt_atual = box.text.strip() if hasattr(box, 'text') else ''
                            if len(txt_atual) < 5:
                                # Se estiver vazio, tenta recuperar o prompt original da variável de instância (se existir) ou apenas avisa
                                self._tlog("⚠️ Caixa vazia no retry! Enviando atalho de submit mesmo assim.")
                                
                            with self.__class__._submit_lock:
                                box.send_keys(Keys.CONTROL, Keys.ENTER)
                                time.sleep(3)
                            
                            self._tlog("🔄 Prompt resubmetido após rate limit.")
                            momento_submit = time.time()
                            time.sleep(10)  # Aguarda processamento
                            continue
                    except Exception as e_resub:
                        self._tlog(f"⚠️ Falha ao resubmeter: {e_resub}")
                        self._rate_limit_retries = 0
                        return False
                
                if status == 'FALHA':
                    self._tlog("🚨 FALHA DETECTADA NA TELA (Unusual Activity / Policy).")
                    self._debug("FLOW_FALHA_DETECTADA")
                    break
                    
                if status in ['SUCESSO_BOTAO', 'SUCESSO_FALLBACK']:
                    # Trava contra falso-positivo (imagens muito rápidas)
                    if (time.time() - momento_submit) < 15:
                        time.sleep(1.5)
                        continue
                    
                    self._rate_limit_retries = 0
                    self._tlog("✔ Geração concluída com sucesso!")
                    self._debug( "FLOW_GERACAO_CONCLUIDA")
                    return True
                
                self._print_progress_inline(f"[FLOW-IA] Gerando... {int(time.time() - momento_submit)}s")
                time.sleep(1.5)
                
            self._rate_limit_retries = 0
            self._tlog("❌ Geração interrompida ou Timeout atingido.")
            return False
            
        except Exception as e:
            self._tlog(f"Erro no monitoramento: {e}")
            return False

    def gerar_imagem_base(self, caminho_referencia: Path, prompt: str, caminho_saida: Path, caminho_modelo: Optional[Path] = None) -> Path:
        """Orquestração corrigida: Modelo primeiro (Direita), Produto depois (Esquerda/Destaque)."""
        self._tlog(f"🎬 [FLOW-IMAGE] Iniciando geração. Saída: {caminho_saida.name}")
        
        sucesso_absoluto = False
        
        # LOOP 1: PROJETOS (Máx 2 Projetos Novos)
        for tentativa_projeto in range(1, 3):
            self._tlog(f"📦 [PROJETO {tentativa_projeto}/2] Iniciando workspace...")
            self.acessar_flow()
            self.clicar_novo_projeto()
            
            try:
                self._fechar_modais_intrusivos()

                # Atributos de rastreamento de estado
                if not hasattr(self, '_modelo_base_upada'): self._modelo_base_upada = False

                # --- 🚨 ESTRATÉGIA DE POSICIONAMENTO 🚨 ---
                
                # 1. FAZ UPLOAD DA MODELO PRIMEIRO
                # Ao subir primeiro, ela será "empurrada" para a direita pelo próximo upload.
                if caminho_modelo and caminho_modelo.exists():
                    if not self._modelo_base_upada:
                        self._tlog("Subindo MODELO primeiro (ficará na direita)...")
                        if not self._upload_produto_isolado(caminho_modelo):
                            raise Exception("Falha no upload da modelo.")
                        self._modelo_base_upada = True
                        # ⚡ Poll rápido: espera grade estabilizar (em vez de sleep(2) cego)
                        for _ in range(5):
                            try:
                                estavel = self.driver.execute_script("var t=document.querySelectorAll('[data-tile-id] img'); return t.length>0 && t[t.length-1].naturalWidth>0;")
                                if estavel: break
                            except: pass
                            time.sleep(0.3)
                    else:
                        self._tlog("Modelo já presente no Workspace.")

                # 2. FAZ UPLOAD DO PRODUTO POR ÚLTIMO
                # O produto assume a posição 1 (Extrema Esquerda).
                self._tlog("Subindo PRODUTO por último (Garantindo Índice 1 / Esquerda)...")
                if not self._upload_produto_isolado(caminho_referencia):
                    raise Exception("Falha no upload do produto.")
                
                self._debug( f"FLOW_GRADE_PRONTA_{caminho_referencia.stem}") #

                # LOOP 2: TENTATIVAS DE GERAÇÃO (Máx 3 por projeto)
                for tentativa_geracao in range(1, 4):
                    self._tlog(f"⚙️ [GERAÇÃO {tentativa_geracao}/3] Preparando prompt e modelo...")
                    
                    # 3. Clica no Produto para ancorar o destaque (Sempre no Índice 1) e abrir o modal
                    if not self._clicar_produto_destaque(caminho_referencia.name):
                        raise Exception("Falha ao abrir o modal do produto em destaque.")

                    # 4. Digita o prompt (Limpa a caixa no modal e cola o texto novo, ANTES de anexar a modelo)
                    if not self._digitar_prompt_imagem(prompt):
                        raise Exception("Falha ao digitar prompt.")

                    url_ancora = self.driver.current_url

                    # 5. Anexar modelo pela lista de recentes
                    if caminho_modelo and caminho_modelo.exists():
                        if not self._anexar_modelo_pela_lista(caminho_modelo.name, url_ancora):
                            raise Exception("A modelo não fixou na interface.")

                    # 6. Configura parâmetros (Modelo/Dimensoes)
                    self._modelo_configurado = False
                    self.configurar_parametros_imagem()
                    
                    # 7. Submeter prompt
                    if self._submeter_prompt_imagem(timeout_geracao=120):
                        sucesso_absoluto = True
                        break # Sucesso na geração!
                    else:
                        self._tlog(f"⚠️ Tentativa {tentativa_geracao} falhou. Resetando modal...")
                        from selenium.webdriver.common.action_chains import ActionChains
                        from selenium.webdriver.common.keys import Keys
                        ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                        time.sleep(2)
                        
                if sucesso_absoluto:
                    break # Sucesso no projeto!

            except Exception as e:
                self._tlog(f"Falha no projeto {tentativa_projeto}: {str(e)[:100]}")
                self.driver.refresh()
                self._projeto_criado = False 
                self._modelo_base_upada = False
                time.sleep(4)
                
        if not sucesso_absoluto:
            raise Exception("Falha ao gerar imagem no Flow após 2 projetos.")
            
        resultado = self._baixar_imagem(caminho_saida)
        
        # 🛡️ VALIDAÇÃO PÓS-DOWNLOAD: Verifica se a imagem baixada não é a imagem original
        try:
            import hashlib
            hash_resultado = hashlib.md5(resultado.read_bytes()).hexdigest()
            hash_original = hashlib.md5(caminho_referencia.read_bytes()).hexdigest()
            
            if hash_resultado == hash_original:
                self._tlog("🚨 IMAGEM BAIXADA É IDÊNTICA AO PRODUTO ORIGINAL! Geração falhou silenciosamente.")
                self._debug("FLOW_DOWNLOAD_IMAGEM_ORIGINAL")
                resultado.unlink(missing_ok=True)
                raise Exception("Download capturou a imagem original do produto em vez da gerada")
            
            # Verifica tamanho mínimo (imagens borradas/cinza costumam ser muito pequenas)
            tamanho_kb = resultado.stat().st_size / 1024
            if tamanho_kb < 10:
                self._tlog(f"🚨 Imagem baixada muito pequena ({tamanho_kb:.0f}KB). Provável falha.")
                self._debug("FLOW_DOWNLOAD_MUITO_PEQUENO")
                resultado.unlink(missing_ok=True)
                raise Exception(f"Imagem gerada muito pequena ({tamanho_kb:.0f}KB) - provável falha de geração")
                
            self._tlog(f"✅ Validação pós-download OK: {tamanho_kb:.0f}KB, hash diferente do original.")
        except (FileNotFoundError, PermissionError):
            pass  # Se não conseguiu validar, segue com o resultado
        
        return resultado
    
    # =================================================================================
    # MÉTODOS DE VÍDEO E DOWNLOADS: COMPLETAMENTE INTOCÁVEIS (SUA LÓGICA ORIGINAL)
    # =================================================================================
    def anexar_imagem(self, caminho: Path, abrir_modal: bool = False) -> bool:
        """
        Sobe a imagem para o projeto e garante a vinculação no slot 'Inicial'.
        Blindado SEM ESC para não resetar a seleção no React.
        """
        nome_arquivo = caminho.name
        self._fechar_modais_intrusivos() 
        
        # 🚨 ADIÇÃO CRÍTICA: Fecha o menu de perfil do Google que está sobrepondo a tela
        try:
            from selenium.webdriver.common.action_chains import ActionChains
            from selenium.webdriver.common.keys import Keys
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(0.5)
        except: pass
        
        if not self._imagem_upada:
            self._tlog(f'Fazendo upload da imagem de referência: {nome_arquivo}')
            try:
                input_file = self._encontrar_input_file()
                self.driver.execute_script("arguments[0].style.display='block'; arguments[0].style.visibility='visible'; arguments[0].style.opacity=1;", input_file)
                
                # 🛡️ PRE-UPLOAD: Dismiss qualquer popup residual (Concordo) ANTES do send_keys
                try:
                    self.driver.execute_script("""
                        var btns = document.querySelectorAll('button');
                        for (var b of btns) {
                            var txt = (b.textContent || '').trim();
                            if (txt === 'Concordo' || txt === 'Agree') { b.click(); return true; }
                        }
                        return false;
                    """)
                except: pass
                
                input_file.send_keys(str(caminho.resolve()))
                
                # 🛡️ POST-UPLOAD: Dismiss popup que pode aparecer APÓS injetar arquivo
                try:
                    self.driver.execute_script("""
                        var btns = document.querySelectorAll('button');
                        for (var b of btns) {
                            var txt = (b.textContent || '').trim();
                            if (txt === 'Concordo' || txt === 'Agree') {
                                b.click();
                                return true;
                            }
                        }
                        return false;
                    """)
                except: pass
                time.sleep(0.3)
                
                self._tlog('Aguardando a conclusão do upload da imagem (sumiço do loader/%)...')
                # ⚡ POLL RÁPIDO: Espera o upload começar via JS puro (~50ms por check)
                for _ in range(15):
                    try:
                        tem_tile = self.driver.execute_script("return !!document.querySelector('[data-tile-id]');")
                        if tem_tile: break
                    except: pass
                    time.sleep(0.2)

                fim_upload = time.time() + 90
                while time.time() < fim_upload:
                    try:
                        status = self.driver.execute_script("""
                            var spinners = document.querySelectorAll('[class*="spin"], [role="progressbar"]');
                            for (var s of spinners) {
                                if (s.offsetParent !== null) return 'LOADING';
                            }
                            var tiles = document.querySelectorAll('[data-tile-id]');
                            for (var t of tiles) {
                                var txt = t.innerText || '';
                                if (/%/.test(txt) && /\\d/.test(txt)) return 'LOADING';
                            }
                            var erros = ['Falha','Failed','Error','Erro','Viola','Violat'];
                            for (var t of tiles) {
                                var inner = t.innerText || '';
                                for (var e of erros) {
                                    if (inner.indexOf(e) >= 0) return 'ERRO';
                                }
                            }
                            return 'OK';
                        """)
                        if status == 'OK': break
                        if status == 'ERRO':
                            self._tlog("❌ Falha crítica: O Google Flow rejeitou a imagem no servidor.")
                            break
                    except: pass
                    time.sleep(0.5)

                time.sleep(0.5) 
                self._imagem_upada = True
            except Exception as e:
                self._tlog(f'🚨 Falha no upload nativo da imagem: {e}')
                return False
        else:
            self._tlog(f'A imagem {nome_arquivo} já foi upada no projeto. Indo para o clique...')

        if abrir_modal:
            self._tlog("Clicando na imagem na tela principal para abrir o modal de prompt...")
            try:
                xpath_miniatura = f"//img[contains(@alt, '{nome_arquivo}') or contains(@src, 'blob:')] | //div[@data-tile-id]//img"
                # 🛡️ HUNTER: Busca miniaturas
                miniaturas = detectar_com_hunter(
                    driver=self.driver,
                    chave_memoria="flow_miniaturas_imagem",
                    descricao_para_ia="Miniatura de imagem na galeria do Google Flow",
                    seletores_rapidos=[xpath_miniatura],
                    palavras_semanticas=["img", "imagem", "blob", "miniatura"],
                    etapa="FLOW_UPLOAD",
                )
                
                if miniaturas:
                    # Rola para o elemento antes de clicar para evitar que fique fora da tela
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", miniaturas[-1])
                    js_click(self.driver, miniaturas[-1])
                    time.sleep(2.0)
                    self._tlog("✔ Imagem clicada! Modal aberto.")
                    self._debug( f"FLOW_MODAL_PROMPT_ABERTO_{caminho.stem}")
                    return True
                    
                self._tlog("⚠️ Imagem não achada. Clicando no último card genérico...")
                imgs = detectar_com_hunter(
                    driver=self.driver,
                    chave_memoria="flow_imgs_fallback",
                    descricao_para_ia="Qualquer tag img na página do Google Flow",
                    seletores_rapidos=["//img"],
                    etapa="FLOW_UPLOAD",
                )
                if imgs:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", imgs[-1])
                    js_click(self.driver, imgs[-1]) 
                    time.sleep(2.0)
                return True
            except Exception as e:
                self._tlog(f'🚨 Erro ao abrir modal: {e}')
                return True
        else:
            self._tlog("Vinculando a imagem no botão 'Inicial' da interface principal...")
            try:
                xpath_btn_inicial = (
                    "//div[@type='button' and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'inicial') "
                    "or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'initial'))]"
                )
                # 🛡️ HUNTER: Busca botões Initial
                botoes_iniciais = detectar_com_hunter(
                    driver=self.driver,
                    chave_memoria="flow_btn_inicial",
                    descricao_para_ia="Botão 'Inicial' ou 'Initial' para vincular imagem base no Google Flow",
                    seletores_rapidos=[xpath_btn_inicial],
                    palavras_semanticas=["inicial", "initial", "imagem base"],
                    etapa="FLOW_UPLOAD",
                )
                
                if botoes_iniciais:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botoes_iniciais[0])
                    js_click(self.driver, botoes_iniciais[0])
                    self._tlog('Botão "Inicial" clicado. Aguardando galeria...')
                    time.sleep(2.5) 

                    xpath_img_popup = f"//div[@role='dialog']//img[contains(@alt, '{nome_arquivo}') or contains(@src, 'blob:')] | //div[@role='dialog']//img"
                    # 🛡️ HUNTER: Busca imagens no popup/dialog
                    imgs_dialog = detectar_com_hunter(
                        driver=self.driver,
                        chave_memoria="flow_imgs_dialog",
                        descricao_para_ia="Imagens dentro do popup/dialog de seleção do Google Flow",
                        seletores_rapidos=[xpath_img_popup],
                        etapa="FLOW_UPLOAD",
                    )
                    if imgs_dialog:
                        js_click(self.driver, imgs_dialog[0])
                        self._tlog('✔ Imagem base selecionada no popup. Aguardando UI processar...')
                        time.sleep(2.5)

                    self._debug( f"FLOW_CONFERENCIA_SLOT_INICIAL_{caminho.stem}")
                    self._tlog('✔ Imagem vinculada e trancada no slot Inicial!')
                else:
                    self._tlog('⚠️ Botão "Inicial" não encontrado na tela.')
                return True
            except Exception as e:
                self._tlog(f'🚨 Erro na vinculação ao botão Inicial: {e}')
                self._debug( "ERRO_VINCULACAO_INICIAL")
                return True

    def _garantir_imagem_anexada(self, caminho_imagem: Path) -> bool:
        self._tlog("Validando visualmente a presença da imagem no Slot Inicial...")
        try:
            # 🛡️ HUNTER: Verifica botão Remove
            btn_remover = detectar_com_hunter(
                driver=self.driver,
                chave_memoria="flow_btn_remover",
                descricao_para_ia="Botão 'Remove' para remover imagem anexada no Google Flow",
                seletores_rapidos=["//button[contains(@aria-label, 'Remove')]"],
                palavras_semanticas=["remove", "remover", "delete"],
                etapa="FLOW_UPLOAD",
            )
            if btn_remover:
                self._tlog("✅ Imagem detectada e garantida no projeto.")
                return True
            
            # 🛡️ HUNTER: Verifica botão Initial image com img
            botoes_initial = detectar_com_hunter(
                driver=self.driver,
                chave_memoria="flow_btn_initial_com_img",
                descricao_para_ia="Botão 'Initial image' contendo uma miniatura de imagem no Google Flow",
                seletores_rapidos=["//button[contains(@aria-label, 'Initial image') and .//img]"],
                palavras_semanticas=["initial", "image", "inicial"],
                etapa="FLOW_UPLOAD",
            )
            if botoes_initial:
                self._tlog("✅ Miniatura de imagem garantida no botão Inicial.")
                return True
            
            self._tlog("⚠️ O slot Inicial está vazio. Tentando re-vincular a imagem do projeto...")
            
            self.driver.refresh()
            time.sleep(5)
            self.acessar_flow()
            
            self._projeto_criado = False
            self._modelo_configurado = False
            self.clicar_novo_projeto()
            self.configurar_parametros_video()
            return self.anexar_imagem(caminho_imagem)
            
        except Exception as e:
            self._tlog(f"Erro na rotina de hard-check da imagem: {e}")
            return False

    def _ler_texto_prompt_box(self, box: WebElement) -> str:
        try:
            return box.get_attribute("textContent") or box.text or ""
        except Exception:
            return ""

    def enviar_prompt_e_aguardar(self, prompt: str, timeout_geracao: int = 420, modo_imagem: bool = False) -> bool:
        import os
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.support import expected_conditions as EC
        
        # Helper para clique via JS (se não tiver no seu arquivo, adicione no topo ou use driver.execute_script)
        def js_click(driver, element):
            driver.execute_script("arguments[0].click();", element)

        prompt_linear = remover_caracteres_nao_bmp(" ".join(prompt.split()))
        
        
        # 🛡️ GUARD: Tamanho máximo antes do send_keys (video prompts ~500-800 chars)
        MAX_PROMPT_VIDEO = 3000
        if len(prompt_linear) > MAX_PROMPT_VIDEO:
            self._tlog(f"🚨 GUARD FLOW VIDEO: Prompt com {len(prompt_linear)} chars (max {MAX_PROMPT_VIDEO}). Prompt corrompido — ABORTANDO envio!")
            self._tlog(f"🚨 Primeiros 200 chars: {prompt_linear[:200]}...")
            return False
        
        # Tenta salvar log do prompt se a função existir
        try:
            from integrations.utils import salvar_ultimo_prompt
            salvar_ultimo_prompt(f"--- PROMPT ENVIADO AO FLOW ---\n{prompt_linear}")
        except: pass
                                    
        for tentativa_local in range(1, 4):
            self._tlog(f"[FLOW-IA] Iniciando tentativa local de prompt {tentativa_local}/3...")
            
            try:
                if not modo_imagem:
                    # --- 🛡️ VALIDAÇÃO CRÍTICA DO SLOT INICIAL (CORRIGIDA PARA MODO VÍDEO) ---
                    # No modo vídeo, a imagem vira um "chip" na barra inferior. O XPath antigo não achava.
                    xpath_chip_video = "//div[@role='textbox']/ancestor::div[position()<=3]//img | //button[contains(@aria-label, 'Remove') or contains(@aria-label, 'Close') or contains(@aria-label, 'Delete')]"
                    btn_img_chip = self.driver.find_elements(By.XPATH, xpath_chip_video)
                    
                    if not btn_img_chip:
                        self._tlog("⚠️ O Flow removeu a imagem do slot! Revinculando...")
                        try:
                            xpath_btn_inicial = "//div[@type='button' and (contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'inicial') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'initial'))] | //button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'inicial') or contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'initial')]"
                            botoes_iniciais = self.driver.find_elements(By.XPATH, xpath_btn_inicial)
                            
                            if botoes_iniciais and botoes_iniciais[0].is_displayed():
                                js_click(self.driver, botoes_iniciais[0])
                                time.sleep(2.0)
                                imgs_dialog = self.driver.find_elements(By.XPATH, "//div[@role='dialog']//img")
                                if imgs_dialog:
                                    js_click(self.driver, imgs_dialog[0])
                                    self._tlog("✔ Imagem selecionada. Aguardando a interface estabilizar...")
                                    time.sleep(2.5) 
                        except Exception as e:
                            self._tlog(f"🚨 Erro ao revincular: {e}")
                    else:
                        self._tlog("✔ Imagem de referência confirmada no slot (Chip detectado).")

                # --- 2. BUSCA DA CAIXA DE TEXTO (Híbrida para garantir foco) ---
                xpath_box = "//div[@role='dialog']//div[@role='textbox'] | //div[@role='dialog']//textarea | //div[@role='textbox' and @contenteditable='true'] | //textarea"
                caixas = self.driver.find_elements(By.XPATH, xpath_box)
                box = next((c for c in caixas if c.is_displayed()), None)
                
                if not box:
                    box = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath_box)))

                # Garante visibilidade e foco sem desmarcar o slot
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", box)
                self.driver.execute_script("arguments[0].focus();", box)
                js_click(self.driver, box) 
                time.sleep(0.5)

                # Limpeza de texto residual
                box.send_keys(Keys.CONTROL, "a")
                box.send_keys(Keys.BACKSPACE)
                time.sleep(0.5)

                self._tlog("📸 Salvando print: ANTES de digitar o prompt.")
                self._debug( f"FLOW_PROMPT_T{tentativa_local}_1_ANTES_DIGITAR")

                # --- 3. ESCRITA HUMANIZADA + SUBMIT VIA BOTÃO ---
                import random
                
                self._tlog(f"Modo Humanizado: Digitando prompt em blocos...")
                
                # Digita em blocos de 8-15 chars com timing humano
                texto = prompt_linear
                pos = 0
                while pos < len(texto):
                    # Tamanho do bloco: 8-15 chars (simula rajada de digitação)
                    chunk_size = random.randint(8, 15)
                    chunk = texto[pos:pos + chunk_size]
                    box.send_keys(chunk)
                    pos += chunk_size
                    # Pausa entre blocos: rápida mas variável
                    time.sleep(random.uniform(0.03, 0.12))

                # Delay final pra UI processar
                time.sleep(random.uniform(0.8, 1.5))

                # --- 🛡️ VALIDAÇÃO CRÍTICA: Verifica se o prompt foi colado integralmente ---
                texto_na_caixa = self._ler_texto_prompt_box(box)
                
                # Extrair trechos-chave do prompt para verificar presença
                trechos_obrigatorios = []
                if "Subject:" in prompt_linear:
                    # Pega as primeiras 40 chars após "Subject:"
                    idx_s = prompt_linear.index("Subject:")
                    trechos_obrigatorios.append(prompt_linear[idx_s:idx_s+50].strip()[:40])
                if "Character:" in prompt_linear:
                    idx_c = prompt_linear.index("Character:")
                    trechos_obrigatorios.append(prompt_linear[idx_c:idx_c+50].strip()[:40])
                if "Dialogue:" in prompt_linear:
                    idx_d = prompt_linear.index("Dialogue:")
                    trechos_obrigatorios.append(prompt_linear[idx_d:idx_d+50].strip()[:40])
                
                prompt_ok = True
                for trecho in trechos_obrigatorios:
                    if trecho not in texto_na_caixa:
                        prompt_ok = False
                        break
                
                # Verificação de comprimento mínimo (pelo menos 50% do prompt)
                if len(texto_na_caixa) < len(prompt_linear) * 0.5:
                    prompt_ok = False
                
                if not prompt_ok:
                    self._tlog(f"⚠️ PROMPT INCOMPLETO NA CAIXA! Esperado ~{len(prompt_linear)} chars, encontrado {len(texto_na_caixa)}. Limpando e redigitando...")
                    self._debug(f"FLOW_PROMPT_INCOMPLETO_T{tentativa_local}")
                    
                    # Limpa tudo
                    box.send_keys(Keys.CONTROL, "a")
                    box.send_keys(Keys.BACKSPACE)
                    time.sleep(0.5)
                    
                    # Método alternativo: clipboard paste (mais confiável)
                    import subprocess
                    processo = subprocess.Popen(['clip'], stdin=subprocess.PIPE, shell=True)
                    processo.communicate(prompt_linear.encode('utf-16le'))
                    box.send_keys(Keys.CONTROL, "v")
                    time.sleep(1.0)
                    
                    # Re-verifica
                    texto_recheck = self._ler_texto_prompt_box(box)
                    if len(texto_recheck) < len(prompt_linear) * 0.5:
                        self._tlog(f"🚨 PROMPT AINDA INCOMPLETO após 2ª tentativa ({len(texto_recheck)} chars). Tentativa local vai reiniciar...")
                        continue  # Pula pro próximo tentativa_local
                    else:
                        self._tlog(f"✔ Prompt redigitado via clipboard ({len(texto_recheck)} chars)")

                self._tlog("📸 Salvando print: DEPOIS de digitar o prompt.")
                self._debug( f"FLOW_PROMPT_T{tentativa_local}_2_POS_DIGITAR")

                # --- 4. SUBMISSÃO VIA ENTER ---
                self._tlog("📸 Salvando print: ANTES do submit.")
                self._debug( f"FLOW_PROMPT_T{tentativa_local}_3_ANTES_SUBMIT")

                # 🤖 ANTI-BOT: Stagger escalonado por thread_id + cadência global entre submits
                import threading
                
                if self.thread_id > 0:
                    stagger_individual = self.thread_id * random.uniform(2.5, 4.0)
                    self._tlog(f"🤖 Anti-bot stagger: T{self.thread_id} aguardando {stagger_individual:.1f}s...")
                    time.sleep(stagger_individual)
                
                if not hasattr(self.__class__, '_submit_stagger_lock'):
                    self.__class__._submit_stagger_lock = threading.Lock()
                    self.__class__._ultimo_submit_global = 0.0
                
                with self.__class__._submit_stagger_lock:
                    agora = time.time()
                    intervalo_minimo = random.uniform(5.0, 9.0)
                    espera = intervalo_minimo - (agora - self.__class__._ultimo_submit_global)
                    if espera > 0:
                        self._tlog(f"🤖 Anti-bot cadência global: aguardando {espera:.1f}s...")
                        time.sleep(espera)
                    self.__class__._ultimo_submit_global = time.time()
                    self.momento_ultimo_submit = time.time()

                box.send_keys(Keys.END)
                time.sleep(0.2)
                box.send_keys(Keys.ENTER)
                self._tlog("✔ ENTER enviado no textbox (submit via teclado).")

                time.sleep(2)
                self._debug(f"FLOW_PROMPT_T{tentativa_local}_4_POS_SUBMIT")


                
                # --- 5. MONITORAMENTO DA GERAÇÃO ---
                if modo_imagem:
                    self._tlog(f"Aguardando o botão 'Baixar' habilitar (máx {timeout_geracao}s)...")
                    xpath_btn_baixar = "//button[.//i[text()='download'] and (.//div[text()='Baixar'] or .//span[text()='Baixar'])]"
                    
                    fim_espera = time.time() + timeout_geracao
                    _rate_retries = 0

                    while time.time() < fim_espera:
                        # 🚨 CHECK 1: Rate Limit / Falha genérica
                        try:
                            page_txt = self.driver.execute_script("return document.body.innerText.toLowerCase();")
                            
                            # Rate limit
                            if 'solicitando gerações muito rápido' in page_txt or 'requesting generations too quickly' in page_txt:
                                _rate_retries += 1
                                self._tlog(f"⏳ RATE LIMIT detectado (tentativa {_rate_retries}/3).")
                                if _rate_retries > 3:
                                    self._tlog("🚫 Rate limit persistente. Abortando.")
                                    return False
                                # Fecha popup + espera + resubmete
                                self.driver.execute_script("""
                                    var allBtns = document.querySelectorAll('button, [role="button"]');
                                    for (var b of allBtns) {
                                        var lbl = (b.getAttribute('aria-label') || '').toLowerCase();
                                        var txt = (b.innerText || '').toLowerCase();
                                        if (lbl.includes('close') || lbl.includes('fechar') || txt.includes('fechar') || txt.includes('dismiss')) {
                                            b.click(); break;
                                        }
                                    }
                                """)
                                time.sleep(10)
                                try:
                                    box.send_keys(Keys.CONTROL, Keys.ENTER)
                                    self._tlog("🔄 Prompt resubmetido.")
                                    self.momento_ultimo_submit = time.time()
                                except: pass
                                time.sleep(10)
                                continue
                            
                            # Falhas fatais
                            falhas = ['unusual activity', 'policy violation', 'against our policy',
                                      'atividade incomum', 'violação de política']
                            if any(f in page_txt for f in falhas):
                                self._tlog("🚨 Erro fatal (policy/unusual) detectado.")
                                return False
                        except: pass

                        # Check do botão baixar
                        btns = self.driver.find_elements(By.XPATH, xpath_btn_baixar)
                        if btns and btns[0].is_displayed() and btns[0].get_attribute("disabled") is None:
                            
                            # 🚨 CHECK 2: Trava de 10 segundos (Evita o asset antigo/produto)
                            if (time.time() - self.momento_ultimo_submit) < 10:
                                time.sleep(2)
                                continue
                                
                            self._tlog("✔ Geração concluída com sucesso!")
                            return True
                        
                        time.sleep(4)
                else:
                    # Usa seu sistema de tracking de progresso inline (barra de % no terminal)
                    resultado_tracking = getattr(self, '_aguardar_geracao_tracking_inline', lambda p, t: False)(prompt_linear, timeout_geracao)
                    if resultado_tracking == True:
                        return True
                    elif isinstance(resultado_tracking, str):
                        return resultado_tracking  # "UNUSUAL_ACTIVITY", "POLICY_VIOLATION", etc.
                    else:
                        return False # Falhou na geração, aborta a tentativa local para o main.py recriar o projeto.
                
            except Exception as e:
                self._tlog(f'Erro na tentativa local {tentativa_local}: {str(e)[:100]}')
                time.sleep(2)
                
        return False
    
    def _aguardar_geracao_imagem_sem_porcentagem(self, prompt: str, timeout: int = 60) -> bool:
        self._tlog(f"Aguardando o card da nova imagem aparecer no feed central...")
        fim = time.time() + timeout
        ultimo_log = time.time()
        self.ultimo_tile_id_gerado = None
        
        while time.time() < fim:
            if not self.ultimo_tile_id_gerado:
                card = self._encontrar_card_por_prompt(prompt)
                if card:
                    self.ultimo_tile_id_gerado = self._obter_tile_id(card)
                else:
                    xpath_gerando = "//*[@data-tile-id and (.//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'gerando')] or .//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'generating')] or .//*[contains(@class, 'spin')])]"
                    cards_gerando = self.driver.find_elements(By.XPATH, xpath_gerando)
                    if cards_gerando:
                        self.ultimo_tile_id_gerado = self._obter_tile_id(cards_gerando[0])
            
            if not self.ultimo_tile_id_gerado:
                if time.time() - ultimo_log > 5:
                    self._print_progress_inline("[FLOW-IA] Aguardando o Google criar o novo card de imagem...")
                    ultimo_log = time.time()
                time.sleep(2)
                continue

            base_xpath = f"//*[@data-tile-id='{self.ultimo_tile_id_gerado}']"
            try:
                cards = self.driver.find_elements(By.XPATH, base_xpath)
                if cards:
                    card = cards[0]
                    txt = (card.text or "").lower()
                    
                    sucesso = card.find_elements(By.XPATH, ".//button[.//i[text()='download']] | .//img[not(contains(@src, 'blob')) and not(contains(@class, 'avatar'))]")
                    if sucesso:
                        self._finish_progress_inline("[FLOW-IA] ✔ Imagem gerada com sucesso no card correto!")
                        return True
                    
                    if "falha" in txt or "failed" in txt or "erro" in txt:
                        self._finish_progress_inline("[FLOW-IA] ❌ Card em estado de erro detectado.")
                        return False
                    
                    if time.time() - ultimo_log > 5:
                        self._print_progress_inline("[FLOW-IA] Imagem em processamento no feed...")
                        ultimo_log = time.time()
            except Exception:
                pass
            
            time.sleep(2)
            
        self._finish_progress_inline("[FLOW-IA] ❌ Timeout esgotado na geração da imagem.")
        return False

    def _listar_cards(self):
        return self.driver.find_elements(By.XPATH, "//*[@data-tile-id]")

    def _obter_tile_id(self, card):
        try:
            tid = card.get_attribute("data-tile-id")
            if tid: return tid
        except Exception: pass
        try:
            el = card.find_element(By.XPATH, ".//*[@data-tile-id]")
            tid = el.get_attribute("data-tile-id")
            if tid: return tid
        except Exception: pass
        return None

    def _encontrar_card_por_tile_id(self, tile_id: str):
        if not tile_id: return None
        try:
            return self.driver.find_element(By.XPATH, f"//*[@data-tile-id='{tile_id}']")
        except Exception: return None

    def _encontrar_card_por_prompt(self, prompt: str):
        trecho = prompt[:40].strip()
        cards = self._listar_cards()
        for c in cards:
            try:
                txt_bruto = self.driver.execute_script("return arguments[0].textContent;", c)
                if txt_bruto and trecho in txt_bruto: return c
            except Exception: pass
        return None

    def _card_mais_recente(self):
        cards = self._listar_cards()
        return cards[0] if cards else None

    def _aguardar_geracao_tracking_inline(self, prompt: str, timeout: int) -> bool:
        self._print_progress_inline("[FLOW-IA] Aguardando início da geração...")
        fim = time.time() + timeout
        self.ultimo_tile_id_gerado = None
        ultimo_movimento = time.time()
        viu_sinal_de_vida = False
        ultimo_percentual_logado = None
        ultimo_status_inline = None
        linha_progresso_ativa = True
        ja_viu_percentual = False   # 🛡️ True se alguma vez vimos % no card
        ts_ultima_pct_vista = 0.0   # 🛡️ Timestamp da última vez que vimos %

        while time.time() < fim:
            if not self.ultimo_tile_id_gerado:
                card = self._encontrar_card_por_prompt(prompt) or self._card_mais_recente()
                if card: self.ultimo_tile_id_gerado = self._obter_tile_id(card)
                
                if not self.ultimo_tile_id_gerado:
                    self._print_progress_inline("[FLOW-IA] Gerando... aguardando card aparecer")
                    time.sleep(2)
                    continue
                else:
                    if linha_progresso_ativa:
                        self._finish_progress_inline()
                        linha_progresso_ativa = False
                    self._tlog(f"Tile ID rastreado: {self.ultimo_tile_id_gerado}")
                    self._debug( "FLOW_CARD_GERACAO_INICIO")

            base_xpath = f"//*[@data-tile-id='{self.ultimo_tile_id_gerado}']"

            # 🛡️ GRACE PERIOD: Não checa erro nos primeiros 20s (estados transitórios)
            tempo_desde_tile = time.time() - ultimo_movimento
            
            try:
                erros = self.driver.find_elements(By.XPATH, f"{base_xpath}//*[contains(text(), 'Falha') or contains(text(), 'Failed') or contains(text(), 'Erro')]")
                if erros and any(e.is_displayed() for e in erros):
                    # Cross-validação: se tem % de progresso visível, NÃO é erro real
                    txt_card = ""
                    try:
                        els = self.driver.find_elements(By.XPATH, base_xpath)
                        if els:
                            txt_card = self.driver.execute_script("return arguments[0].textContent;", els[0]) or ""
                    except: pass
                    
                    tem_progresso = bool(re.search(r'[1-9]\d?\s*%', txt_card))
                    
                    if tem_progresso:
                        pass  # Falso positivo: vídeo gerando com %, ignora o "erro"
                    elif tempo_desde_tile < 20:
                        pass  # Grace period: muito cedo para declarar erro
                    else:
                        if linha_progresso_ativa: self._finish_progress_inline("[FLOW-IA] Geração falhou.")
                        self._debug("FLOW_ERRO_NO_CARD")
                        self._tlog("❌ Card em estado de erro (Falha) detectado na interface.")
                        self._debug("ERRO_NO_CARD")
                        
                        # 🛡️ Detecta se é UNUSUAL ACTIVITY (detecção de robô — NÃO é culpa do prompt)
                        _termos_unusual = ['unusual activity', 'atividade incomum', 'unusual', 'help center']
                        if any(t in txt_card.lower() for t in _termos_unusual):
                            self._tlog("🤖 UNUSUAL ACTIVITY: Google detectou automação. Novo projeto necessário (NÃO reescrever prompt).")
                            return "UNUSUAL_ACTIVITY"
                        
                        # 🛡️ Detecta se é POLICY VIOLATION (conteúdo sexual/violação de política)
                        _termos_policy = ['violar', 'sexual', 'policy', 'políticas', 'política', 'violação', 'violation']
                        if any(t in txt_card.lower() for t in _termos_policy):
                            self._tlog("🚨 POLICY VIOLATION: O prompt foi bloqueado por violação de política do Flow!")
                            return "POLICY_VIOLATION"

                        
                        return False
            except Exception: pass

            # 🛡️ PASSO 1: Lê a percentagem ANTES de checar sucesso
            pct_atual = None
            try:
                elementos_card = self.driver.find_elements(By.XPATH, base_xpath)
                for el in elementos_card:
                    txt_bruto = self.driver.execute_script("return arguments[0].textContent;", el)
                    m = re.search(r'(100|[1-9]?\d)\s*%', txt_bruto or "")
                    if m:
                        pct_atual = m.group(0)
                        break
            except Exception: pass

            # 🛡️ PASSO 2: Anti-flicker — checa sucesso baseado em TEMPO, não em %
            # Se VÍNHAMOS vendo % e ela sumiu, esperamos 5s antes de declarar pronto.
            # Flicker do DOM dura <2s. Geração legítima faz a % sumir permanentemente.
            tem_pct_ativa = pct_atual and '100' not in pct_atual
            
            if tem_pct_ativa:
                # Ainda gerando — atualiza timestamp
                ja_viu_percentual = True
                ts_ultima_pct_vista = time.time()
            
            # Condições para checar se o card está REALMENTE pronto:
            # 1. Não tem % ativa agora E
            # 2. (Nunca vimos % nenhuma OU a % sumiu há mais de 5s)
            pode_checar_sucesso = (
                not tem_pct_ativa and (
                    not ja_viu_percentual or                          # Card sem tracking de % (ex: imagem)
                    (time.time() - ts_ultima_pct_vista) > 5.0        # % sumiu há 5s+ → é real
                )
            )
            if pode_checar_sucesso:
                try:
                    sucesso = self.driver.find_elements(By.XPATH, f"{base_xpath}//video | {base_xpath}//img[contains(@alt, 'Gerado') or contains(@alt, 'Generated')] | {base_xpath}//i[contains(text(), 'play_circle')]")
                    if sucesso:
                        if linha_progresso_ativa: self._finish_progress_inline("[FLOW-IA] Gerando... 100% | pronto!")
                        else: _log("✔ Artefato pronto e disponível para download.")
                        self._debug( "FLOW_CARD_GERACAO_PRONTO")
                        return True
                except Exception: pass

            # PASSO 3: Atualiza progresso no terminal
            if pct_atual:
                viu_sinal_de_vida = True
                ultimo_movimento = time.time()
                if pct_atual != ultimo_percentual_logado:
                    self._print_progress_inline(f"[FLOW-IA] Gerando... {pct_atual}")
                    ultimo_percentual_logado = pct_atual
                    ultimo_status_inline = "percentual"
                    linha_progresso_ativa = True
            else:
                try:
                    loaders = self.driver.find_elements(By.XPATH, f"{base_xpath}//*[contains(@class, 'spin') or contains(text(), 'Generating') or contains(text(), 'Gerando')]")
                    if loaders:
                        viu_sinal_de_vida = True
                        ultimo_movimento = time.time()
                        if ultimo_status_inline != "processando":
                            self._print_progress_inline("[FLOW-IA] Gerando... processando")
                            ultimo_status_inline = "processando"
                            linha_progresso_ativa = True
                    else:
                        parado = int(time.time() - ultimo_movimento)
                        msg = f"[FLOW-IA] Gerando... aguardando progresso ({parado}s)"
                        if ultimo_status_inline != msg:
                            self._print_progress_inline(msg)
                            ultimo_status_inline = msg
                            linha_progresso_ativa = True
                        self._debug("GERANDO_ARTEFATO")   
                except Exception: pass

            if not viu_sinal_de_vida:
                if time.time() - ultimo_movimento > 60:
                    if linha_progresso_ativa: self._finish_progress_inline()
                    self._debug("FLOW_SEM_SINAL_DE_VIDA")
                    self._tlog("❌ Card sem sinal de vida por 60s. Assumindo erro.")
                    return False
            else:
                if time.time() - ultimo_movimento > 60:
                    if linha_progresso_ativa: self._finish_progress_inline()
                    self._debug("FLOW_CARD_ESTAGNADO")
                    self._tlog("❌ Card estagnado por muito tempo. Assumindo erro.")
                    return False
            time.sleep(2)

        if linha_progresso_ativa: self._finish_progress_inline()
        self._debug("FLOW_TIMEOUT_GERACAO")
        self._tlog("Timeout esgotado na geração do artefato.")
        return False

    def resolver_permissoes_drive(self) -> None:
        try:
            continue_btn = self.driver.find_elements(By.XPATH, "//span[contains(text(), 'Continue')]")
            if continue_btn and continue_btn[0].is_displayed():
                js_click(self.driver, continue_btn[0])
                time.sleep(1.5)
                allow_btn = self.driver.find_elements(By.XPATH, "//span[contains(text(), 'Allow')]")
                if allow_btn and allow_btn[0].is_displayed():
                    js_click(self.driver, allow_btn[0])
                    time.sleep(1.5)
        except Exception: pass

    def _snapshot_arquivos(self, diretorio: Path, extensao: str = ".mp4") -> set[str]:
        diretorio.mkdir(parents=True, exist_ok=True)
        return {p.name for p in diretorio.glob(f"*{extensao}")}

    def _esperar_download_arquivo(self, download_dir: Path, antes: set[str], extensao: str = ".mp4", timeout=60) -> Path:
        fim = time.time() + timeout
        ultimo_temp = None
        while time.time() < fim:
            crdownloads = list(download_dir.glob("*.crdownload"))
            novos_arquivos = [p for p in download_dir.glob(f"*{extensao}") if p.name not in antes]
            
            if novos_arquivos and not crdownloads:
                novos_arquivos.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                arquivo = novos_arquivos[0]
                self._tlog(f"✔ Download concluído internamente no Windows: {arquivo.name}")
                return arquivo
            
            if crdownloads:
                crdownloads.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                atual = crdownloads[0]
                if ultimo_temp != atual.name:
                    self._tlog(f"ℹ Baixando: {atual.name}")
                    ultimo_temp = atual.name
            time.sleep(1)
            
        raise TimeoutException(f"Timeout aguardando arquivo {extensao} no diretório.")

    def _aguardar_arquivo_download(self, download_dir: Path, timeout: int = 60):
        """Monitora pasta até surgir arquivo válido (não .crdownload/.tmp). Retorna Path ou None."""
        fim_timeout = time.time() + timeout
        while time.time() < fim_timeout:
            arquivos_na_pasta = list(download_dir.glob("*"))
            validos = [f for f in arquivos_na_pasta if not f.name.endswith('.crdownload') and not f.name.endswith('.tmp')]
            if validos:
                validos.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                return validos[0]
            time.sleep(1)
        return None

    def baixar_video_gerado(self, caminho_destino: Path) -> bool:
        """Abre o player, clica em baixar 720p e monitora QUALQUER novo arquivo na pasta local (estratégia faminta)."""
        self._tlog(f'Iniciando download do vídeo para: {caminho_destino.name}')
        caminho_destino = Path(caminho_destino)
        
        # Sincronizado com o browser.py — usa diretório isolado por thread
        from integrations.profile_manager import obter_caminho_download_thread
        download_dir = obter_caminho_download_thread(self.thread_id).resolve()
        
        try:
            # 1. 🧹 LIMPEZA PRÉVIA: Mata qualquer lixo antes de começar
            if download_dir.exists():
                for f in download_dir.glob("*"):
                    try: f.unlink()
                    except: pass
            else:
                download_dir.mkdir(parents=True, exist_ok=True)

            self._tlog("Abrindo página do vídeo pronto...")
            
            # 🔄 RETRY: Card pode demorar a renderizar no DOM (especialmente em headless)
            card = None
            fim_card = time.time() + 15
            while time.time() < fim_card:
                try:
                    if self.ultimo_tile_id_gerado: 
                        card = self._encontrar_card_por_tile_id(self.ultimo_tile_id_gerado)
                    if not card: 
                        card = self._card_mais_recente()
                    if card:
                        break
                except:
                    pass
                time.sleep(1)
            
            if not card:
                self._tlog("ERRO: Não encontrei card do vídeo pronto após 15s de espera.")
                self._debug(f"FLOW_SEM_CARD_{caminho_destino.stem}")
                return False

            # Tenta abrir o player e encontrar o botão de download (com retry)
            for tentativa_player in range(1, 4):
                # Re-busca o card a cada tentativa para evitar stale element
                if tentativa_player > 1:
                    self._tlog(f"🔄 Re-tentando abrir player (tentativa {tentativa_player}/3)...")
                    card = None
                    try:
                        if self.ultimo_tile_id_gerado:
                            card = self._encontrar_card_por_tile_id(self.ultimo_tile_id_gerado)
                        if not card:
                            card = self._card_mais_recente()
                    except:
                        pass
                    if not card:
                        self._tlog("ERRO: Card sumiu do DOM no retry.")
                        return False
                
                try:
                    # Encontra elemento clicável dentro do card
                    alvo_click = None
                    fim_alvo = time.time() + 10
                    while time.time() < fim_alvo:
                        try: alvo_click = card.find_element(By.XPATH, ".//button[contains(@class,'sc-d64366c4-1') and .//video]")
                        except: pass
                        if not alvo_click:
                            try: alvo_click = card.find_element(By.XPATH, ".//video")
                            except: pass
                        if not alvo_click:
                            try: alvo_click = card.find_element(By.XPATH, ".//i[contains(text(), 'play_circle')]")
                            except: pass
                        if alvo_click:
                            break
                        time.sleep(1)

                    if not alvo_click:
                        self._tlog("ERRO: Elemento de vídeo não encontrado dentro do card.")
                        self._debug(f"FLOW_SEM_VIDEO_NO_CARD_{caminho_destino.stem}")
                        return False

                    self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", alvo_click)
                    time.sleep(0.5)
                    js_click(self.driver, alvo_click)
                    
                    # Tempo para o player abrir
                    time.sleep(4.0)
                    self._debug( f"FLOW_PLAYER_VIDEO_{caminho_destino.stem}")
                    
                    # =========================================================
                    # --- BUSCA DO BOTÃO BAIXAR (multi-XPath com retry) ---
                    # =========================================================
                    self._tlog("Procurando botão 'Baixar'...")
                    
                    xpaths_download = [
                        "//button[.//i[text()='download']]",
                        "//button[contains(@aria-label, 'Download') or contains(@aria-label, 'Baixar')]",
                        "//button[.//i[contains(@class, 'google-symbols') and text()='download']]",
                        "//button[.//span[contains(text(), 'Baixar') or contains(text(), 'Download')]]",
                    ]

                    btn_baixar = None
                    fim_btn = time.time() + 45
                    while time.time() < fim_btn:
                        for xp in xpaths_download:
                            try:
                                btns = self.driver.find_elements(By.XPATH, xp)
                                for b in btns:
                                    if b.is_displayed() and b.get_attribute("disabled") is None:
                                        btn_baixar = b
                                        break
                            except:
                                pass
                            if btn_baixar:
                                break
                        if btn_baixar:
                            break
                        time.sleep(2)
                    
                    if btn_baixar:
                        break  # Sai do loop de tentativas do player
                    else:
                        self._tlog(f"⚠️ Botão Baixar não apareceu (tentativa {tentativa_player}/3).")
                        self._debug(f"FLOW_SEM_BTN_BAIXAR_{caminho_destino.stem}")
                        # Fecha player e tenta reabrir
                        try:
                            from selenium.webdriver.common.action_chains import ActionChains
                            from selenium.webdriver.common.keys import Keys
                            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                            time.sleep(1.5)
                        except:
                            pass
                        continue
                
                except Exception as e_player:
                    self._tlog(f"⚠️ Erro ao abrir player (tentativa {tentativa_player}): {str(e_player)[:80]}")
                    try:
                        from selenium.webdriver.common.action_chains import ActionChains
                        from selenium.webdriver.common.keys import Keys
                        ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                        time.sleep(1)
                    except:
                        pass
                    continue

            if not btn_baixar:
                self._tlog("ERRO: Botão Baixar não habilitou após 3 tentativas de player.")
                return False

            try:
                btn_baixar.click()
            except:
                js_click(self.driver, btn_baixar)
            # =========================================================

            time.sleep(1.5) 
            self._debug( f"FLOW_APOS_CLICK_BAIXAR_{caminho_destino.stem}")
            
            self._tlog("Selecionando resolução 720p...")
            xpath_720p = "//button[@role='menuitem'][.//span[contains(.,'720p')]]"
            try:
                btn_720 = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath_720p)))
                btn_720.click()
            except TimeoutException:
                options = self.driver.find_elements(By.XPATH, "//button[@role='menuitem']")
                if options: js_click(self.driver, options[0])
                else: return False
            
            self.resolver_permissoes_drive()
            
            self._tlog(f'Monitorando surgimento de vídeo em: {download_dir}')
            
            # 2. 🕵️ MONITORAMENTO FAMINTO
            arquivo_final = self._aguardar_arquivo_download(download_dir, timeout=60)
            
            # 🔄 RETRY: Se não baixou, refresh na página e tenta de novo (vídeo já está gerado)
            if not arquivo_final:
                self._tlog("⚠️ Download não detectado. Dando refresh e retentando...")
                self._debug(f"FLOW_720P_RETRY_REFRESH_{caminho_destino.stem}")
                
                try:
                    self.driver.refresh()
                    time.sleep(5)
                    
                    # Limpa pasta de download novamente
                    for f in download_dir.glob("*"):
                        try: f.unlink()
                        except: pass
                    
                    # Reabre o card do vídeo
                    card_retry = None
                    fim_card = time.time() + 15
                    while time.time() < fim_card:
                        try:
                            if self.ultimo_tile_id_gerado:
                                card_retry = self._encontrar_card_por_tile_id(self.ultimo_tile_id_gerado)
                            if not card_retry:
                                card_retry = self._card_mais_recente()
                            if card_retry:
                                break
                        except: pass
                        time.sleep(1)
                    
                    if card_retry:
                        # Abre o player
                        alvo = None
                        try: alvo = card_retry.find_element(By.XPATH, ".//video")
                        except: pass
                        if not alvo:
                            try: alvo = card_retry.find_element(By.XPATH, ".//i[contains(text(), 'play_circle')]")
                            except: pass
                        if alvo:
                            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", alvo)
                            time.sleep(0.5)
                            js_click(self.driver, alvo)
                            time.sleep(4)
                        
                        # Re-clica Baixar
                        btn_baixar_retry = None
                        for xp in xpaths_download:
                            try:
                                btns = self.driver.find_elements(By.XPATH, xp)
                                for b in btns:
                                    if b.is_displayed() and b.get_attribute("disabled") is None:
                                        btn_baixar_retry = b
                                        break
                            except: pass
                            if btn_baixar_retry: break
                        
                        if btn_baixar_retry:
                            try: btn_baixar_retry.click()
                            except: js_click(self.driver, btn_baixar_retry)
                            time.sleep(1.5)
                            
                            # Re-clica 720p
                            try:
                                btn_720_retry = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath_720p)))
                                btn_720_retry.click()
                            except TimeoutException:
                                options = self.driver.find_elements(By.XPATH, "//button[@role='menuitem']")
                                if options: js_click(self.driver, options[0])
                            
                            self.resolver_permissoes_drive()
                            self._tlog("🔄 Retry: Monitorando download após refresh...")
                            arquivo_final = self._aguardar_arquivo_download(download_dir, timeout=60)
                
                except Exception as e_retry:
                    self._tlog(f"⚠️ Retry refresh falhou: {str(e_retry)[:80]}")

            if not arquivo_final:
                raise TimeoutException("O download do vídeo não foi detectado após o clique.")

            self._tlog(f"✔ Vídeo capturado: {arquivo_final.name}")

            # 3. 📦 FINALIZAÇÃO E RENOMEAÇÃO
            if caminho_destino.exists(): 
                caminho_destino.unlink()
            
            shutil.move(str(arquivo_final), str(caminho_destino))
            self._tlog(f'✅ Vídeo salvo e renomeado: {caminho_destino.name}')
            
            # Limpa UI (Fecha o player)
            from selenium.webdriver.common.action_chains import ActionChains
            from selenium.webdriver.common.keys import Keys
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(0.5)
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()

            
            return True

        except Exception as e:
            self._tlog(f'Erro no download do vídeo: {e}')
            self._debug( f"ERRO_FATAL_VIDEO_DOWN_{caminho_destino.stem}")
            return False

    def _baixar_imagem(self, caminho_destino: Path) -> Path:
        """Versão Blindada Radix UI: Força o download 1K usando os seletores reais do menu flutuante."""
        self._tlog(f'Iniciando download da imagem para: {caminho_destino.name}')
        from integrations.utils import salvar_print_debug
        from integrations.profile_manager import obter_caminho_download_thread
        download_dir = obter_caminho_download_thread(self.thread_id).resolve()
        
        try:
            # 1. 🧹 LIMPEZA PRÉVIA
            if download_dir.exists():
                for f in download_dir.glob("*"):
                    try: f.unlink()
                    except: pass
            else:
                download_dir.mkdir(parents=True, exist_ok=True)

            # 📸 Print de diagnóstico ANTES do download (para debug se falhar)
            self._debug( f"FLOW_ANTES_DOWNLOAD_{caminho_destino.stem}")
            
            self._tlog("Abrindo imagem pronta no centro da tela...")
            card = None
            if hasattr(self, 'ultimo_tile_id_gerado') and self.ultimo_tile_id_gerado:
                try: card = self.driver.find_element(By.XPATH, f"//div[@data-tile-id='{self.ultimo_tile_id_gerado}']")
                except: pass
            
            # Fallback se não achar pelo ID: pega o card mais recente (o primeiro da lista)
            if not card: 
                try:
                    cards = self.driver.find_elements(By.XPATH, "//div[@data-tile-id]")
                    if cards: card = cards[0]
                except: pass
                
            if card:
                try: js_click(self.driver, card)
                except: pass
            
            time.sleep(2.5)

            # =========================================================
            # --- BUSCA DO BOTÃO BAIXAR (XPath direto, sem cache) ---
            # =========================================================
            arquivo_final = None
            max_tentativas_download = 2

            for tentativa_dl in range(1, max_tentativas_download + 1):
                self._tlog(f"📥 Tentativa de download {tentativa_dl}/{max_tentativas_download}...")
                
                xpath_download = "//button[.//i[text()='download']]"
                try:
                    btn_baixar = WebDriverWait(self.driver, 30).until(
                        EC.element_to_be_clickable((By.XPATH, xpath_download))
                    )
                    
                    try:
                        btn_baixar.click()
                    except:
                        js_click(self.driver, btn_baixar)
                        
                    time.sleep(1.5)
                    
                    # Clica na opção 1K
                    xpath_1k = "//button[@role='menuitem'][.//span[contains(.,'1K')]]"
                    try:
                        btn_1k = self.wait.until(EC.element_to_be_clickable((By.XPATH, xpath_1k)))
                        btn_1k.click()
                    except TimeoutException:
                        options = self.driver.find_elements(By.XPATH, "//button[@role='menuitem']")
                        if options: js_click(self.driver, options[0])
                        
                except TimeoutException:
                    self._tlog("ERRO: Botão Baixar não habilitou a tempo na tela da imagem.")
                    continue
                
                time.sleep(2.0)
                self.resolver_permissoes_drive()
                
                # --- 🔍 VERIFICAÇÃO RÁPIDA: O download realmente iniciou? ---
                # Se em 8s não apareceu nenhum arquivo (nem .crdownload), o clique foi em vão.
                download_iniciou = False
                fim_verificacao = time.time() + 8
                while time.time() < fim_verificacao:
                    todos = list(download_dir.glob("*"))
                    if todos:
                        download_iniciou = True
                        break
                    time.sleep(0.5)
                
                if download_iniciou:
                    self._tlog("✔ Download detectado na pasta! Aguardando conclusão...")
                    break  # Sai para o monitoramento completo abaixo
                else:
                    self._tlog(f"⚠️ Nenhum arquivo surgiu após clique (tentativa {tentativa_dl}). Cache pode estar envenenado.")
                    self._debug( f"FLOW_DOWNLOAD_FALHOU_T{tentativa_dl}_{caminho_destino.stem}")
                    
                    if tentativa_dl < max_tentativas_download:
                        # 🧹 PURGA DO CACHE: Limpa seletores envenenados e tenta do zero
                        self._tlog("🧹 Limpando cache envenenado e retentando com seletores frescos...")
                        from integrations.self_healing import limpar_memoria_chave
                        for chave in ["flow_botao_baixar", "flow_menu_download", "flow_card_imagem_pronta"]:
                            limpar_memoria_chave(chave, "FLOW_DOWNLOAD_IMG")
                        
                        # Fecha qualquer menu residual antes de retentar
                        try:
                            from selenium.webdriver.common.action_chains import ActionChains
                            from selenium.webdriver.common.keys import Keys
                            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                            time.sleep(1.0)
                        except: pass

            # --- 4. MONITORAMENTO DO DOWNLOAD (espera o arquivo final) ---
            self._tlog(f'Monitorando surgimento de arquivo em: {download_dir}')
            fim_timeout = time.time() + 60 
            while time.time() < fim_timeout:
                validos = [f for f in download_dir.glob("*") if not f.name.endswith(('.crdownload', '.tmp'))]
                if validos:
                    validos.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                    arquivo_final = validos[0]
                    break
                time.sleep(1)

            if not arquivo_final:
                # 🆕 FALLBACK: Download via JavaScript (thread-safe!)
                self._tlog("⚠️ Download nativo falhou. Tentando via JavaScript (fetch direto)...")
                arquivo_final_js = self._baixar_imagem_via_js(caminho_destino)
                if arquivo_final_js:
                    return arquivo_final_js
                raise Exception("Arquivo não detectado na pasta após o clique de download.")

            # 5. 📦 FINALIZAÇÃO E LIMPEZA
            if caminho_destino.exists(): caminho_destino.unlink()
            
            import shutil
            shutil.move(str(arquivo_final), str(caminho_destino))
            self._tlog(f'✅ Download concluído e renomeado: {caminho_destino.name}')
            
            # Fecha menu se sobrar aberto (ESC duplo)
            try:
                from selenium.webdriver.common.action_chains import ActionChains
                from selenium.webdriver.common.keys import Keys
                ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                time.sleep(0.5)
                ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            except: pass
            
            return caminho_destino

        except Exception as e:
            self._tlog(f'🚨 Erro fatal no download 1K: {e}')
            self._debug( f"ERRO_DOWNLOAD_1K_{caminho_destino.stem}")
            raise

    def _baixar_imagem_via_js(self, caminho_destino: Path) -> Optional[Path]:
        """Fallback thread-safe: extrai a imagem direto do DOM via canvas JavaScript.
        
        Não depende do sistema de download do Chrome, evitando conflitos
        de Page.setDownloadBehavior entre threads que compartilham o mesmo browser.
        Usa canvas para extrair pixels diretamente — sem fetch, sem timeout de rede.
        """
        try:
            import base64
            
            # Aumenta timeout do script para 60s
            self.driver.set_script_timeout(60)
            
            # Estratégia: canvas com reload crossOrigin se necessário
            js_extract = """
            // Procura a imagem principal expandida (a maior na tela)
            const imgs = document.querySelectorAll('img[src]');
            let bestImg = null;
            let bestArea = 0;
            
            for (const img of imgs) {
                const rect = img.getBoundingClientRect();
                const area = rect.width * rect.height;
                if (area > bestArea && rect.width > 200 && rect.height > 200) {
                    bestImg = img;
                    bestArea = area;
                }
            }
            
            if (!bestImg || !bestImg.src) return 'NO_IMG';
            
            // Tenta canvas direto primeiro
            const canvas = document.createElement('canvas');
            const w = bestImg.naturalWidth || bestImg.width;
            const h = bestImg.naturalHeight || bestImg.height;
            canvas.width = w;
            canvas.height = h;
            const ctx = canvas.getContext('2d');
            
            try {
                ctx.drawImage(bestImg, 0, 0, w, h);
                const dataUrl = canvas.toDataURL('image/png');
                if (dataUrl && dataUrl.length > 100) {
                    return dataUrl.split(',')[1];
                }
            } catch(e) {
                // CORS — precisa recarregar com crossOrigin
            }
            
            // Fallback: recarrega a imagem com crossOrigin
            return new Promise((resolve) => {
                const img2 = new Image();
                img2.crossOrigin = 'anonymous';
                img2.onload = function() {
                    const c2 = document.createElement('canvas');
                    c2.width = img2.naturalWidth || img2.width;
                    c2.height = img2.naturalHeight || img2.height;
                    const ctx2 = c2.getContext('2d');
                    ctx2.drawImage(img2, 0, 0);
                    try {
                        const d = c2.toDataURL('image/png');
                        resolve(d && d.length > 100 ? d.split(',')[1] : 'CORS_FAIL');
                    } catch(e2) {
                        resolve('CORS_FAIL');
                    }
                };
                img2.onerror = function() { resolve('LOAD_FAIL'); };
                // Força re-fetch com CORS adicionando query param
                img2.src = bestImg.src + (bestImg.src.includes('?') ? '&' : '?') + '_cors=1';
                // Timeout de 15s
                setTimeout(() => resolve('TIMEOUT'), 15000);
            });
            """
            
            result = self.driver.execute_async_script(js_extract)
            
            if not result or result in ('NO_IMG', 'CORS_FAIL', 'LOAD_FAIL', 'TIMEOUT'):
                self._tlog(f"⚠️ JS Fallback: Canvas falhou ({result}). Tentando via screenshot...")
                # Último recurso: screenshot do elemento
                return self._baixar_imagem_via_screenshot(caminho_destino)
            
            if isinstance(result, str) and len(result) > 100:
                img_bytes = base64.b64decode(result)
                caminho_destino.parent.mkdir(parents=True, exist_ok=True)
                if caminho_destino.exists():
                    caminho_destino.unlink()
                caminho_destino.write_bytes(img_bytes)
                
                if caminho_destino.exists() and caminho_destino.stat().st_size > 1000:
                    self._tlog(f"✅ JS Fallback: Imagem salva via canvas! ({caminho_destino.stat().st_size // 1024}KB)")
                    return caminho_destino
            
            self._tlog("⚠️ JS Fallback: Canvas não retornou dados válidos. Tentando screenshot...")
            return self._baixar_imagem_via_screenshot(caminho_destino)
                
        except Exception as e:
            self._tlog(f"⚠️ JS Fallback: Erro: {e}")
            return self._baixar_imagem_via_screenshot(caminho_destino)

    def _baixar_imagem_via_screenshot(self, caminho_destino: Path) -> Optional[Path]:
        """Último recurso: tira screenshot do elemento <img> maior na tela."""
        try:
            imgs = self.driver.find_elements(By.TAG_NAME, "img")
            best = None
            best_area = 0
            for img in imgs:
                try:
                    size = img.size
                    area = size['width'] * size['height']
                    if area > best_area and size['width'] > 200 and size['height'] > 200:
                        best = img
                        best_area = area
                except:
                    continue
            
            if best:
                png_bytes = best.screenshot_as_png
                caminho_destino.parent.mkdir(parents=True, exist_ok=True)
                if caminho_destino.exists():
                    caminho_destino.unlink()
                caminho_destino.write_bytes(png_bytes)
                
                if caminho_destino.exists() and caminho_destino.stat().st_size > 1000:
                    self._tlog(f"✅ Screenshot Fallback: Imagem capturada! ({caminho_destino.stat().st_size // 1024}KB)")
                    return caminho_destino
            
            self._tlog("⚠️ Screenshot Fallback: Nenhuma imagem grande encontrada.")
            return None
        except Exception as e:
            self._tlog(f"⚠️ Screenshot Fallback: Erro: {e}")
            return None

    def _cacar_botao_download_inteligente(self) -> Optional[WebElement]:
        """
        Busca o botão de download/baixar em 3 camadas de inteligência (Heurística).
        """
        # --- CAMADA 1: XPaths robustos e rápidos ---
        seletores_rapidos = [
            "//button[.//i[text()='download']]",
            "//button[.//i[contains(@class, 'google-symbols') and text()='download']]",
            "//button[contains(@aria-label, 'Download') or contains(@aria-label, 'Baixar')]"
        ]
        for xpath in seletores_rapidos:
            try:
                botoes = self.driver.find_elements(By.XPATH, xpath)
                botoes_vis = [b for b in botoes if b.is_displayed() and b.get_attribute("disabled") is None]
                if botoes_vis:
                    return botoes_vis[-1] # Sempre pega o último (útil se tiver cards empilhados)
            except: pass

        self._tlog("⚠️ Hunter: Botão óbvio não achado. Iniciando Varredura Semântica...")

        # --- CAMADA 2: Varredura Semântica (Procura no HTML oculto) ---
        try:
            botoes = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in reversed(botoes): # Ordem reversa para pegar os botões da frente primeiro
                if not btn.is_displayed() or btn.get_attribute("disabled") is not None: 
                    continue
                
                html_interno = (btn.get_attribute('innerHTML') or '').lower()
                aria = (btn.get_attribute('aria-label') or '').lower()
                
                if 'download' in html_interno or 'baixar' in html_interno or 'download' in aria or 'baixar' in aria:
                    self._tlog("🎯 Hunter: Botão encontrado via HTML interno/Semântica!")
                    return btn
        except: pass

        self._tlog("⚠️ Hunter: Varredura Semântica falhou. Iniciando Varredura de Ícones...")

        # --- CAMADA 3: Varredura visual/ícones ---
        try:
            botoes = self.driver.find_elements(By.XPATH, "//button[.//i or .//svg or .//mat-icon]")
            for btn in reversed(botoes):
                if not btn.is_displayed() or btn.get_attribute("disabled") is not None:
                    continue
                
                html_interno = (btn.get_attribute('innerHTML') or '').lower()
                if 'download' in html_interno or 'save_alt' in html_interno:
                    self._tlog("🎯 Hunter: Botão encontrado via nome do ícone da fonte!")
                    return btn
        except: pass

        return None
    
    def detectar_erro_fatal_flow(self):
        """
        Verifica mensagens de bloqueio ou erro fatal na interface do Flow.
        Retorna True se houver erro, forçando a troca de conta no main.py.
        """
        try:
            # Termos chave baseados no comportamento real do Google Labs
            termos_fatais = [
                'unusual activity', 
                'atividade incomum', 
                'policy', 
                'não foi possível gerar',
                'something went wrong',
                'please visit',
                'falha'
            ]
            
            for termo in termos_fatais:
                # XPath Robusto: converte tudo para minúsculo antes de comparar
                xpath = f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{termo}')]"
                erros = self.driver.find_elements(By.XPATH, xpath)
                
                for e in erros:
                    if e.is_displayed():
                        self._tlog(f"🚨 BLOQUEIO DETECTADO: Termo '{termo}' encontrado na tela.")
                        return True

            # Check extra por classes de erro CSS ou ícones de alerta
            seletores_extra = ["//div[contains(@class, 'error')]", "//mat-icon[text()='error']"]
            for sel in seletores_extra:
                extras = self.driver.find_elements(By.XPATH, sel)
                if any(ex.is_displayed() for ex in extras):
                    return True

            return False
        except Exception as e:
            self._tlog(f"Erro ao verificar falhas fatais: {e}")
            return False
        
# =====================================================================
#   FUNÇÕES AUXILIARES DE PROCESSAMENTO (TEXTO)
# =====================================================================

def _remover_emojis(texto: str) -> str:
    padrao_emoji = re.compile(
        r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF'
        r'\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF'
        r'\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF'
        r'\u2600-\u26FF\u2700-\u27BF\u2B50\u2B55\u23F0-\u23F3\u23F8-\u23FA\uFE0F]'
    )
    return padrao_emoji.sub(r'', texto)


def sanitizar_prompt_policy(prompt: str) -> str:
    """
    Remove ou substitui palavras/frases que ativam o filtro de 'conteúdo sexual'
    do Google Flow. Preserva a intenção criativa usando termos neutros.
    """
    # Substituições case-insensitive (original → neutro)
    _substituicoes = [
        # Cenário
        (r'\bin the bedroom\b', 'in a modern interior'),
        (r'\bbedroom\b', 'interior'),
        (r'\bin bed\b', 'in a cozy setting'),
        # Roupas íntimas / pijama com contexto corporal
        (r'\blingerie\b', 'sleepwear'),
        (r'\bpajama set\b', 'matching lounge outfit'),
        (r'\bpijama\b', 'lounge outfit'),
        (r'\bnightgown\b', 'lounge dress'),
        (r'\brobe\b', 'lounge robe'),
        # Expressões sensuais
        (r'\balluring\b', 'confident'),
        (r'\bseductive\b', 'confident'),
        (r'\bsensual\b', 'elegant'),
        (r'\bsensuality\b', 'elegance'),
        (r'\bsensualidade\b', 'elegância'),
        (r'\bsedoso\b', 'premium'),
        (r'\bsedosa\b', 'premium'),
        (r'\bsexy\b', 'stylish'),
        (r'\bintimate\b', 'personal'),
        (r'\bintimidade\b', 'conforto'),
        (r'\bdesejo\b', 'estilo'),
        (r'\bprovocante\b', 'sofisticada'),
        (r'\bsensorial\b', 'premium'),
        # Corpo
        (r'\bcurves\b', 'silhouette'),
        (r'\bbody-hugging\b', 'well-fitted'),
        (r'\bbody\s*con\b', 'fitted'),
        (r'\bcling(?:s|ing)?\s+to\s+(?:her|the)\s+body\b', 'drapes naturally'),
        (r'\bagainst her body\b', 'on the fabric'),
        (r'\bcleavage\b', 'neckline'),
        (r'\bdecote\b', 'gola'),
        # Autoestima em contexto íntimo
        (r'\bautoestima\b', 'confiança'),
        # V-neck em contexto de pijama pode ser gatilho
        (r'\bdeep V-neck\b', 'V-neckline'),
    ]
    
    resultado = prompt
    for padrao, substituto in _substituicoes:
        resultado = re.sub(padrao, substituto, resultado, flags=re.IGNORECASE)
    
    return resultado

def ler_e_separar_cenas(caminho_txt: Path, num_roteiro: int = 1, qtd_cenas: int = 3, variante: str = "") -> list[str]:
    """Lê do roteiros.txt (ou metadados.txt legado) fatiando pelo marcador do roteiro solicitado."""
    # Define os caminhos possíveis na mesma pasta
    roteiros = caminho_txt.parent / "roteiros.txt"
    metadados = caminho_txt.parent / "metadados.txt"
    
    # Prioridade: roteiros.txt > metadados.txt (legado) > arquivo individual (antigo)
    if roteiros.exists():
        arquivo_alvo = roteiros
    elif metadados.exists():
        arquivo_alvo = metadados
    else:
        arquivo_alvo = caminho_txt
    
    if not arquivo_alvo.exists():
        print(f"[FLOW-IA] ⚠️ Arquivo não encontrado: {arquivo_alvo}")
        return []

    conteudo = arquivo_alvo.read_text(encoding='utf-8')
    
    # --- LÓGICA DE FATIAMENTO DO ARQUIVO UNIFICADO ---
    # 🛡️ CORREÇÃO: Verifica se o CONTEÚDO tem o marcador, não se roteiros.txt existe.
    # O metadados.txt TAMBÉM contém os blocos === ROTEIRO X_VARIANTE_Y ===
    if variante:
        tag_atual = f"=== ROTEIRO {num_roteiro}_{variante} ==="
    else:
        tag_atual = f"=== ROTEIRO {num_roteiro} ==="
        
    if tag_atual in conteudo:
        # Pega o texto que começa após a tag do roteiro solicitado
        bloco = conteudo.split(tag_atual)[1]
        
        # Corta antes do próximo === para não pegar outras coisas
        if "\n===" in bloco:
            bloco = bloco.split("\n===")[0]
    else:
        bloco = conteudo
        
    # --- LIMPEZA GERAL ---
    bloco = re.sub(r'<thinking>.*?</thinking>', '', bloco, flags=re.DOTALL)
    bloco = bloco.replace("Show thinking", "").replace("Gemini said", "").strip()
    
    # 🛡️ CORREÇÃO: Remove qualquer marcador === que tenha vazado para dentro do bloco
    bloco = re.sub(r'===\s*VARIANTE\s*\d+\s*===', '', bloco)
    bloco = re.sub(r'===\s*ROTEIRO\s*\d+[^=]*===', '', bloco)
    
    # Remove a parte da legenda do bloco para focar só nas cenas
    bloco = re.split(r'\[(?i:legenda).*?\]', bloco)[0].strip()
    
    partes = re.split(r'\[(?i:cena\s*\d+).*?\]', bloco)
    
    cenas_extraidas = []
    for i, texto_parcial in enumerate(partes):
        # Filtro de segurança para ignorar introduções da IA
        if i == 0 and "transform the input" not in texto_parcial.lower() and "câmera" not in texto_parcial.lower():
            continue 
            
        texto_limpo = texto_parcial.strip()
        if texto_limpo:
            cenas_extraidas.append(texto_limpo)
            
    print(f"[FLOW-IA] Análise de {arquivo_alvo.name} (Roteiro {num_roteiro}): {len(cenas_extraidas)} cenas extraídas.")
    
    if len(cenas_extraidas) < qtd_cenas:
        print(f"[FLOW-IA] ⚠️ Aviso: O arquivo tem menos cenas que o esperado. Extraídas: {len(cenas_extraidas)}")
        
    return cenas_extraidas[:qtd_cenas]