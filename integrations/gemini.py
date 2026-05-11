# arquivo: integrations/gemini.py
# descricao: fachada GeminiAnunciosViaFlow blindada para validacao de imagem,
# geracao POV e criacao de roteiro dinâmico com suporte a Testes A/B (múltiplos roteiros).
# Otimizado para VELOCIDADE EXTREMA, DOWNLOAD NATIVO (60s) e AUTO-F5 EM ERROS DA UI.
# Adicionado suporte para avaliar múltiplas variantes de vídeo e eleger a melhor via interface Web.

from __future__ import annotations

import re
import time
import shutil
import pyperclip
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from integrations.utils import _log as log_base, salvar_print_debug, js_click, scroll_ao_fim, _get_logs_dir, salvar_ultimo_prompt, limpar_diretorio_visao, forcar_fechamento_janela_windows
from integrations.self_healing import cacar_elemento_universal, clicar_com_hunter, interagir_com_menu_complexo, superar_obstaculo_desconhecido, detectar_com_hunter

from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    from anuncios.prompts import (
        PROMPT_CLASSIFICACAO_ARQUIVOS,
        PROMPT_VALIDACAO_PRODUTO,
        PROMPT_JURI_CANDIDATOS_IMAGEM_BASE,
        PROMPT_JURI_TESTE_AB_IMAGEM_BASE,
        PROMPT_JURI_VIDEO,
        carregar_prompt_imagem,
        carregar_prompt_roteiro_mestre,
        carregar_prompt_roteiro_execucao,
        carregar_criterios_juri,
        precisa_de_modelo,
    )
except ImportError:
    # Stubs para quando rodamos fora do projeto Anuncios (conteúdo orgânico)
    PROMPT_CLASSIFICACAO_ARQUIVOS = ""
    PROMPT_VALIDACAO_PRODUTO = ""
    PROMPT_JURI_CANDIDATOS_IMAGEM_BASE = ""
    PROMPT_JURI_TESTE_AB_IMAGEM_BASE = ""
    PROMPT_JURI_VIDEO = ""
    def carregar_prompt_imagem(*a, **kw): return ""
    def carregar_prompt_roteiro_mestre(*a, **kw): return ""
    def carregar_prompt_roteiro_execucao(*a, **kw): return ""
    def carregar_criterios_juri(*a, **kw): return ""
    def precisa_de_modelo(*a, **kw): return False

EXTENSOES_IMAGEM = ('.jpg', '.jpeg', '.png', '.webp')

# Atalho para manter o prefixo [GEMINI-IA] automaticamente neste arquivo
def _log(msg: str):
    log_base(msg, prefixo="GEMINI-IA")


class GeminiAnunciosViaFlow:
    def __init__(self, driver: Any, url_gemini: str, timeout: int = 30, driver_acessibilidade=None, url_gemini_acessibilidade=None, thread_id: int = 0):
        self.driver = driver
        self.url_gemini = url_gemini
        self.wait = WebDriverWait(driver, timeout, poll_frequency=0.1)
        self.timeout = timeout
        self.thread_id = thread_id

        # Salva o "médico" para o Hunter usar
        self.driver_acessibilidade = driver_acessibilidade
        self.url_gemini_acessibilidade = url_gemini_acessibilidade
        
        # NOTA: limpar_diretorio_visao() removido daqui — chamado uma vez no main.py.
        # Se chamado aqui, cada thread apaga os screenshots das outras threads.
        self.pasta_logs_visao = _get_logs_dir() / "visao"
        
        # 🎯 Índice da model-response esperada (-1 = última, modo legado)
        self._indice_resposta_esperada = -1
        # ⚡ Flag: chat já foi treinado e pode ser reutilizado para R2+
        self._chat_treinado = False

    def _verificar_driver_vivo(self):
        """Verifica rapidamente se o driver ainda está conectado ao Chrome.
        Evita loops infinitos tentando interagir com um browser morto.
        """
        try:
            _ = self.driver.title  # Operação mínima — falha instantaneamente se morto
        except Exception as e:
            erro = str(e).lower()
            if any(d in erro for d in ['max retries', 'connectionrefused', 'newconnectionerror', 
                                        'winerror 10061', 'no such session', 'session not created',
                                        'unable to connect', 'target window already closed']):
                raise Exception(f"SWITCH_ACCOUNT: Chrome morreu (driver desconectado) — {str(e)[:80]}")

    def _fechar_menu_lateral(self) -> None:
        """Fecha o menu lateral (sidebar) do Gemini se estiver aberto.
        
        Detecta a sidebar verificando se elementos exclusivos dela (botão New Chat,
        itens de histórico, link Settings) estão visíveis na tela. Em seguida,
        clica no botão hamburger para recolher.
        """
        try:
            # Detecta se a sidebar está aberta verificando se seus elementos internos estão visíveis
            sidebar_aberta = self.driver.execute_script("""
                // Estratégia: procurar elementos que SÓ existem dentro da sidebar
                
                // 1. Botão "New chat" na sidebar (seletor exato do DOM do Gemini)
                var newChatBtn = document.querySelector(
                    'side-nav-action-button[data-test-id="new-chat-button"],' +
                    'a.side-nav-action-collapsed-button[href="/app"]'
                );
                if (newChatBtn) {
                    var rect = newChatBtn.getBoundingClientRect();
                    if (rect.width > 0 && rect.left >= 0 && rect.left < window.innerWidth) {
                        return true;
                    }
                }
                
                // 2. Itens de conversa no histórico da sidebar
                var convItems = document.querySelectorAll(
                    'bard-sidenav a[href*="/app/"],' +
                    'side-nav a[href*="/app/"],' +
                    '.conversation-title,' +
                    'side-nav-recent-chats a'
                );
                for (var i = 0; i < convItems.length; i++) {
                    var r = convItems[i].getBoundingClientRect();
                    if (r.width > 0 && r.left >= 0 && r.left < 300) {
                        return true;
                    }
                }
                
                // 3. Link "Settings & help" no rodapé da sidebar
                var settingsLink = document.querySelector(
                    'side-nav-settings-button,' +
                    'a[href*="settings"],' +
                    'button[data-test-id*="settings"]'
                );
                if (settingsLink) {
                    var sr = settingsLink.getBoundingClientRect();
                    if (sr.width > 0 && sr.left >= 0 && sr.left < 300) {
                        return true;
                    }
                }
                
                // 4. Fallback: qualquer container de sidenav com largura significativa
                var containers = document.querySelectorAll(
                    'bard-sidenav, mat-sidenav, [class*="side-nav-container"], [class*="sidenav"]'
                );
                for (var j = 0; j < containers.length; j++) {
                    var cr = containers[j].getBoundingClientRect();
                    if (cr.width > 100) {
                        return true;
                    }
                }
                
                return false;
            """)

            if not sidebar_aberta:
                return  # Sidebar já está fechada, nada a fazer

            _log("📌 Menu lateral aberto detectado. Fechando para liberar área do chat...")

            # Clica no botão hamburger para fechar
            btn_menu = None
            seletores_menu = [
                'button[data-test-id="side-nav-menu-button"]',
                'side-nav-menu-button button',
                'button[aria-label="Menu principal"]',
                'button[aria-label="Main menu"]',
                'button.main-menu-button',
            ]
            for sel in seletores_menu:
                try:
                    els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in els:
                        if el.is_displayed():
                            btn_menu = el
                            break
                    if btn_menu:
                        break
                except:
                    pass

            if btn_menu:
                js_click(self.driver, btn_menu)
                time.sleep(0.5)
                _log("✅ Menu lateral fechado com sucesso.")
            else:
                # Fallback: tenta ESC para fechar
                _log("⚠️ Botão hamburger não encontrado. Tentando ESC...")
                try:
                    self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                    time.sleep(0.3)
                except:
                    pass
        except Exception as e:
            # Não-fatal — segue em frente se falhar
            _log(f"⚠️ Não foi possível fechar o menu lateral: {e}")


    def abrir_gemini(self) -> None:
        self._verificar_driver_vivo()
        _log('Abrindo Gemini e validando estado da tela...')
        self.driver.get(self.url_gemini) 
        # ⚡ POLL: Espera o Angular carregar (em vez de sleep(4) cego)
        for _ in range(20):
            try:
                if self.driver.find_elements(By.CSS_SELECTOR, 'rich-textarea, button.speech_dictation_mic_button, div[contenteditable]'):
                    break
            except: pass
            time.sleep(0.2)

        # 🧹 FECHA O MENU LATERAL (sidebar) se estiver aberto — evita obstrução de UI
        self._fechar_menu_lateral()

        # 🚨 DETECÇÃO RÁPIDA DE BLOQUEIOS FATAIS (antes de qualquer trator/healer)
        url_atual = self.driver.current_url or ""
        page_text = ""
        try:
            page_text = self.driver.find_element(By.TAG_NAME, "body").text or ""
        except:
            pass
        
        # 1. Admin bloqueou Gemini para esta conta Workspace
        if "ServiceNotAllowed" in url_atual or "admin.google.com" in url_atual:
            salvar_print_debug(self.driver, "FATAL_GEMINI_BLOQUEADO_ADMIN")
            raise Exception("SWITCH_ACCOUNT: Conta sem acesso ao Gemini (bloqueio administrativo)")
        
        # 2. Conta redirecionou para login (sessão morreu)
        if "accounts.google.com" in url_atual and "signin" in url_atual:
            salvar_print_debug(self.driver, "FATAL_SESSAO_EXPIRADA")
            raise Exception("SWITCH_ACCOUNT: Sessão expirou — redirecionou para login")
        
        # 3. "Algo deu errado" — erro TEMPORÁRIO do Gemini (sobrecarga do serviço)
        # NÃO BANIR — dar múltiplas tentativas com espera crescente
        if "algo deu errado" in page_text.lower() or "something went wrong" in page_text.lower():
            salvar_print_debug(self.driver, "GEMINI_ALGO_DEU_ERRADO")
            
            for retry_algo in range(1, 4):  # 3 tentativas
                espera = retry_algo * 5  # 5s, 10s, 15s
                _log(f"⚠️ 'Algo deu errado' detectado (tentativa {retry_algo}/3). Refresh em {espera}s...")
                time.sleep(espera)
                self.driver.refresh()
                time.sleep(3)
                
                try:
                    page_retry = self.driver.find_element(By.TAG_NAME, "body").text or ""
                except:
                    page_retry = ""
                
                if "algo deu errado" not in page_retry.lower() and "something went wrong" not in page_retry.lower():
                    _log("✅ 'Algo deu errado' resolvido após retry!")
                    break
            else:
                # Todas as 3 tentativas falharam — mas usa SWITCH sem ban
                raise Exception("SWITCH_ACCOUNT: Gemini 'Algo deu errado' após 3 retries (temporário)")
        
        # 4. myaccount.google.com (Healer navegou errado antes)
        if "myaccount.google.com" in url_atual:
            salvar_print_debug(self.driver, "FATAL_MYACCOUNT_REDIRECT")
            _log("⚠️ Redirecionado para MyAccount. Tentando navegar ao Gemini novamente...")
            self.driver.get(self.url_gemini)
            time.sleep(2.0)
            url_pos = self.driver.current_url or ""
            if "myaccount.google.com" in url_pos or "ServiceNotAllowed" in url_pos:
                raise Exception("SWITCH_ACCOUNT: Conta não consegue acessar Gemini")

        tela_liberada = False
        
        self._superar_bloqueios_e_onboarding()

        try:
            # 🛡️ HUNTER: Selecionamos o alvo principal (Microfone ou Caixa de Texto)
            alvo = cacar_elemento_universal(
                driver=self.driver,
                chave_memoria="gemini_alvo_ui_ociosa",
                descricao_para_ia="Botão de microfone ou caixa de texto contenteditable no chat do Gemini (indicando UI ociosa)",
                seletores_rapidos=[
                    'button.speech_dictation_mic_button',
                    'rich-textarea div[contenteditable="true"]',
                ],
                palavras_semanticas=["microphone", "microfone"],
                permitir_autocura=False,
                etapa="GEMINI_CHAT",
            )
            
            if alvo and alvo.is_displayed():
                is_obstruido = self.driver.execute_script("""
                    var el = arguments[0];
                    var rect = el.getBoundingClientRect();
                    var cx = rect.left + rect.width / 2;
                    var cy = rect.top + rect.height / 2;
                    var elAtPoint = document.elementFromPoint(cx, cy);
                    return !el.contains(elAtPoint);
                """, alvo)
                
                if not is_obstruido:
                    tela_liberada = True
        except:
            pass

        # Se a tela está obstruída ou os elementos não existem, CHAMA O TRATOR
        if not tela_liberada:
            _log('⚠️ Interface obstruída ou não detectada. Acionando o trator...')
            salvar_print_debug(self.driver, "BLOQUEIO_DETECTADO")
            
            if not self._superar_bloqueios_e_onboarding():
                _log("⚠️ Trator falhou. Tentando Refresh de emergência...")
                self.driver.refresh()
                time.sleep(2)
                
                # 🚨 Re-check de bloqueios fatais pós-refresh
                url_pos = self.driver.current_url or ""
                if "ServiceNotAllowed" in url_pos or "admin.google.com" in url_pos:
                    raise Exception("SWITCH_ACCOUNT: Conta sem acesso ao Gemini (bloqueio administrativo)")
                if "accounts.google.com" in url_pos and "signin" in url_pos:
                    raise Exception("SWITCH_ACCOUNT: Sessão expirou — redirecionou para login")
                
                # 🛡️ HUNTER: Check final pós-refresh
                mic_check = detectar_com_hunter(
                    driver=self.driver,
                    chave_memoria="gemini_mic_check_refresh",
                    descricao_para_ia="Botão de microfone no Gemini após refresh (indicando UI funcional)",
                    seletores_rapidos=['button.speech_dictation_mic_button', 'rich-textarea div[contenteditable="true"]'],
                    palavras_semanticas=["microphone", "microfone"],
                    etapa="GEMINI_CHAT",
                )
                if not mic_check:
                    salvar_print_debug(self.driver, "FATAL_INTERFACE_BLOQUEADA")
                    raise Exception("SWITCH_ACCOUNT: Interface do Gemini bloqueada após todas tentativas")
            
            _log("✅ Interface liberada.")

    def _superar_bloqueios_e_onboarding(self) -> bool:
        """
        Função MEGA GENÉRICA estilo 'Trator'.
        Lida com Privacy Hub, Termos de Uso e Onboarding de contas novas.
        """
        salvar_print_debug(self.driver,"VERIFICANDO_BLOQUEIOS_UI")
        _log("🔥 ENTROU EM _superar_bloqueios_e_onboarding")
        
        # 🛡️ GUARD DE URL: Se saiu do Gemini, navega de volta ANTES de clicar em qualquer coisa
        try:
            url_atual = self.driver.current_url or ""
            if url_atual and "gemini.google" not in url_atual and "bard.google" not in url_atual:
                _log(f"⚠️ Trator: Browser fora do Gemini ({url_atual[:60]}). Navegando de volta...")
                self.driver.get(self.url_gemini)
                time.sleep(3.0)
                # Verifica se já caiu no chat direto
                try:
                    textarea = self.driver.find_elements(By.CSS_SELECTOR, 'rich-textarea div[contenteditable="true"]')
                    if textarea and textarea[0].is_displayed():
                        _log("✅ Interface de chat liberada após navegação de volta!")
                        return True
                except: pass
        except: pass
        
        # 🚨 ACELERAÇÃO MÁXIMA: Desliga a espera automática do Selenium
        self.driver.implicitly_wait(0)
        
        try:
            palavras_chave = [
                'chat with gemini', 'conversar com', 'i agree', 'concordo', 'aceito',
                'continue', 'continuar', 'next', 'próximo', 'got it', 'entendi',
                'try gemini', 'experimentar', 'ok', 'aceitar', 'accept', 'use gemini',
                'more', 'mais', 'done', 'concluir', 'finalizar', 'agree', 'no, thanks', 'não, obrigado'
            ]
            
            for rodada in range(6):
                try:
                    self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                    #time.sleep(0.1)
                except: pass
                    
                clicou_algo = False
                
                seletores_prioridade = [
                    "button[data-test-id='upload-image-agree-button']", 
                    "button.agree-button",                              
                    "button[jslog*='173921']",                          
                    ".mat-mdc-dialog-actions button",                   
                    "button.mat-mdc-unelevated-button"                  
                ]
                
                xpath_condicoes = " or ".join([f"contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{p}')" for p in palavras_chave])
                
                # --- 🛡️ BLINDAGEM V3: BLOQUEIO DE COMPONENTES CUSTOMIZADOS ---
                # Adicionamos not(ancestor::bard-sidenav) para matar o clique no histórico.
                # Também mantemos o not(ancestor::nav) por segurança para outras telas.
                xpath_exclusao = "not(ancestor::nav) and not(ancestor::bard-sidenav)"
                
                xpath_monstro = (
                    f"//button[{xpath_exclusao}][{xpath_condicoes}] | "
                    f"//a[{xpath_exclusao}][{xpath_condicoes}] | "
                    f"//span[{xpath_exclusao}][{xpath_condicoes}]/ancestor::button"
                )
                
                # 1. Monta lista de candidatos priorizando o MODAL
                candidatos = []
                for sel in seletores_prioridade:
                    try: 
                        els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                        # Filtro extra para seletores CSS: ignora se estiver dentro do sidenav
                        for el in els:
                            if not self.driver.execute_script("return arguments[0].closest('bard-sidenav')", el):
                                candidatos.append(el)
                    except: pass
                
                try: candidatos.extend(self.driver.find_elements(By.XPATH, xpath_monstro))
                except: pass
                
                try: 
                    fab = self.driver.find_element(By.CSS_SELECTOR, "button.mat-mdc-extended-fab")
                    if not self.driver.execute_script("return arguments[0].closest('bard-sidenav')", fab):
                        candidatos.append(fab)
                except: pass

                # 2. Executa o clique de alta pressão
                for btn in candidatos:
                    try:
                        if btn.is_displayed() and btn.is_enabled():
                            texto_btn = (btn.text or btn.get_attribute('aria-label') or '').strip().replace('\n', ' ')
                            
                            # 🛡️ BLACKLIST: Ignora botões que NÃO são do Gemini onboarding
                            # (páginas de segurança/conta Google que o trator confunde)
                            _blacklist = ['ecossistema', 'saiba mais', 'learn more', 'help center', 
                                          'central de ajuda', 'privacidade', 'privacy', 'termos de serviço',
                                          'terms of service', 'sobre o google', 'about google']
                            if any(bl in texto_btn.lower() for bl in _blacklist):
                                continue  # Pula — não é botão de onboarding
                            
                            _log(f"🎯 Trator encontrou: '{texto_btn[:30]}'. Executando clique de alta pressão...")
                            
                            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                            self.driver.execute_script("arguments[0].focus();", btn)
                            
                            self.driver.execute_script("""
                                var btn = arguments[0];
                                btn.style.pointerEvents = 'auto'; 
                                btn.style.visibility = 'visible';
                                var label = btn.querySelector('.mdc-button__label') || btn;
                                var mousedown = new MouseEvent('mousedown', { 'bubbles': true, 'cancelable': true, 'view': window });
                                var click = new MouseEvent('click', { 'bubbles': true, 'cancelable': true, 'view': window });
                                var mouseup = new MouseEvent('mouseup', { 'bubbles': true, 'cancelable': true, 'view': window });
                                label.dispatchEvent(mousedown);
                                label.dispatchEvent(click);
                                label.dispatchEvent(mouseup);
                            """, btn)
                            
                            try:
                                ActionChains(self.driver).move_to_element(btn).click().perform()
                                btn.send_keys(Keys.ENTER)
                                btn.send_keys(Keys.SPACE)
                            except: pass
                                
                            clicou_algo = True
                            _log("⏳ Clique disparado. Validando transição...")
                            salvar_print_debug(self.driver,"VERIFICANDO SE CLICOU NO BOTAO DE BLOQUEIO")
                            time.sleep(0.1) 
                            break 
                    except: continue
                
                # 3. Verificação de Sucesso
                try:
                    textarea = self.driver.find_elements(By.CSS_SELECTOR, 'rich-textarea div[contenteditable="true"]')
                    if textarea and textarea[0].is_displayed():
                        _log("✅ Interface de chat liberada!")
                        return True
                except: pass

                if not clicou_algo: break
            
            # 🧠 FALLBACK INTELIGENTE: Trator não resolveu, pede ajuda à IA
            _log("🧠 Trator falhou. Acionando resolução autônoma via IA...")
            resolveu = superar_obstaculo_desconhecido(
                driver=self.driver,
                driver_acessibilidade=getattr(self, 'driver_acessibilidade', None),
                url_gemini=getattr(self, 'url_gemini_acessibilidade', None),
                contexto="tela de bloqueio, onboarding ou popup de termos no Gemini impedindo acesso ao chat"
            )
            if resolveu:
                # Verifica se a caixa de texto apareceu após a resolução
                try:
                    textarea = self.driver.find_elements(By.CSS_SELECTOR, 'rich-textarea div[contenteditable="true"]')
                    if textarea and textarea[0].is_displayed():
                        _log("✅ IA resolveu o bloqueio! Interface de chat liberada.")
                        return True
                except: pass
            
            return False
            
        finally:
            # 🚨 RELIGA O FREIO DE MÃO (Timeout original de 5s estipulado no .env)
            self.driver.implicitly_wait(5)

    def _forcar_modelo_pro(self) -> None:
        _log('Verificando/Forçando modelo Pro...')
        
        time.sleep(0.5)
        
        for tentativa in range(1, 4):
            try:
                # 🛡️ HUNTER: Encontra o botão do menu de modelo
                menu_btn = cacar_elemento_universal(
                    driver=self.driver,
                    chave_memoria="gemini_menu_modelo",
                    descricao_para_ia="Botão do menu de seleção de modelo (Pro/Flash) no topo do chat do Gemini",
                    seletores_rapidos=[
                        'button[data-test-id="bard-mode-menu-button"]',
                        'button[aria-label="Open mode picker"]',
                    ],
                    palavras_semanticas=["model", "modo", "pro", "flash"],
                    etapa="GEMINI_MODELO",
                    permitir_autocura=False,
                )
                
                if not menu_btn or not menu_btn.is_displayed():
                    _log(f'Botão de modelo ainda não apareceu (Tentativa {tentativa}/3)...')
                    ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                    time.sleep(0.8)
                    continue

                texto_atual = (menu_btn.text or '').strip().lower()
                
                if 'advanced' in texto_atual or ('pro' in texto_atual and 'thinking' not in texto_atual and 'pensamento' not in texto_atual):
                    _log('✅ Modelo Advanced/Pro já está ativo.')
                    return 
                    
                _log(f'Modelo atual é "{texto_atual}". Abrindo menu de seleção (Tentativa {tentativa}/3)...')
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", menu_btn)
                time.sleep(0.5)
                js_click(self.driver, menu_btn)
                time.sleep(0.8) 
                
                # 🛡️ HUNTER: Busca a opção Pro no menu aberto
                opcao_pro = cacar_elemento_universal(
                    driver=self.driver,
                    chave_memoria="gemini_opcao_pro",
                    descricao_para_ia="Opção 'Advanced' ou 'Pro' (sem Thinking/Pensamento) no dropdown de modelos do Gemini",
                    seletores_rapidos=[
                        'button[data-mode-id="advanced"]',
                        'button[data-test-id="bard-mode-option-advanced"]',
                        'button[data-mode-id="e6fa609c3fa255c0"]',
                        'button[data-test-id="bard-mode-option-pro"]',
                    ],
                    palavras_semanticas=["advanced", "pro"],
                    etapa="GEMINI_MODELO",
                    permitir_autocura=False,
                )
                
                # Filtra para não pegar Pro Thinking / Pro Fast
                clicou_pro = False
                if opcao_pro:
                    texto_opcao = (opcao_pro.text or '').strip().lower()
                    if 'thinking' not in texto_opcao and 'pensamento' not in texto_opcao and 'fast' not in texto_opcao:
                        if opcao_pro.is_displayed():
                            js_click(self.driver, opcao_pro)
                            clicou_pro = True

                if clicou_pro:
                    time.sleep(0.8) 
                    _log('✅ Modelo Pro selecionado com sucesso.')
                    salvar_print_debug(self.driver,"PRO_SELECIONADO_SUCESSO")
                    return 
                else:
                    _log('⚠️ Opção Pro não encontrada no DOM. Fechando menu e recomeçando...')
                    ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                    time.sleep(1.0)
                    
            except Exception as e:
                _log(f'⚠️ Erro na interface ao tentar mudar pro Pro ({e}). Tentando novamente...')
                time.sleep(1.0)
                
        _log('🚨 Aviso: Esgotaram as tentativas de forçar o modelo Pro. Seguindo em frente...')

    def abrir_novo_chat_limpo(self) -> None:
        """
        Versão corrigida: Se já estamos no Gemini, não damos refresh nem reabrimos a URL.
        Apenas clicamos no botão de Novo Chat.
        """
        self._verificar_driver_vivo()
        scroll_ao_fim(self.driver)
        _log('Limpando interface para novo chat...')
        
        # 🛡️ GUARD DE URL: Se saiu do Gemini ou tab crashou, navega de volta
        try:
            url_atual = self.driver.current_url or ""
            if url_atual and "gemini.google" not in url_atual and "bard.google" not in url_atual:
                _log(f"⚠️ Browser fora do Gemini ({url_atual[:60]}). Navegando de volta...")
                self.driver.get(self.url_gemini)
                time.sleep(3.0)
                self._superar_bloqueios_e_onboarding()
        except Exception as e_url:
            # Tab crash resulta em exceção ao tentar ler current_url
            _log(f"⚠️ Tab crashou ({str(e_url)[:50]}). Navegando ao Gemini...")
            try:
                self.driver.get(self.url_gemini)
                time.sleep(3.0)
                self._superar_bloqueios_e_onboarding()
            except:
                pass
            
        try:
            clicou = clicar_com_hunter(
                driver=self.driver,
                chave_memoria="gemini_btn_novo_chat",
                descricao_para_ia="Botão de novo chat (New chat) na barra lateral do Gemini",
                seletores_rapidos=[
                    'side-nav-action-button[data-test-id="new-chat-button"] a',
                    'a.side-nav-action-collapsed-button[href="/app"]',
                    'span[data-test-id="new-chat-button"]',
                    'a[data-test-id="new-chat-button"]',
                    'div[aria-label*="Novo chat"]',
                    'div[aria-label*="New chat"]',
                    'button[aria-label*="Novo chat"]',
                    'button[aria-label*="New chat"]',
                    'a[aria-label*="New chat"]',
                    'a[aria-label*="Novo chat"]',
                ],
                palavras_semanticas=["novo chat", "new chat", "nova conversa"],
                etapa="GEMINI_NAVEGACAO",
                permitir_autocura=True,
                driver_acessibilidade=self.driver_acessibilidade,
                url_gemini=self.url_gemini_acessibilidade,
                timeout_busca=5.0,
            )
            
            if clicou:
                _log('Botão "Novo Chat" acionado.')
            else:
                _log('Aviso: Botão de Novo Chat não visível. Tentando navegar direto...')
                # Fallback: vai direto pra URL do Gemini (limpa o chat)
                try:
                    self.driver.get(self.url_gemini)
                    time.sleep(3.0)
                    self._superar_bloqueios_e_onboarding()
                except:
                    pass
            
            # Validação curta da caixa de texto
            self._obter_textarea_prompt()
            _log('Pronto para novos comandos.')
            
            # Garante o modelo Pro
            self._forcar_modelo_pro()
            
        except Exception as e:
            _log(f'Erro ao limpar chat: {e}')
            raise

    def fechar_popup_tardio_chrome_no_gemini(self) -> None:
        seletores = [
            'button[aria-label*="Continuar como"]',
            'button[aria-label*="Chrome sem uma conta"]',
            'button[jsname]',
        ]
        textos_alvo = ['Continuar como', 'Usar o Chrome sem uma conta']
        for seletor in seletores:
            try:
                elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                for el in elementos:
                    if not el.is_displayed():
                        continue
                    texto = (el.text or el.get_attribute('aria-label') or '').strip()
                    if any(t in texto for t in textos_alvo):
                        js_click(self.driver,el)
                        _log(f'Popup tardio do Chrome tratado: {texto}')
                        salvar_print_debug(self.driver,"POPUP_TARDIO_FECHADO")
                        return
            except Exception:
                pass

    def _encontrar_input_file_visivel_ou_oculto(self, timeout: int = 10) -> WebElement:
        fim = time.time() + timeout
        ultimo_erro = None
        # 🚨 Desliga espera implícita para não travar o loop de polling
        self.driver.implicitly_wait(0)
        try:
            while time.time() < fim:
                # 🛡️ HUNTER: Tenta via cache/semântica primeiro
                el = cacar_elemento_universal(
                    driver=self.driver,
                    chave_memoria="gemini_input_file",
                    descricao_para_ia="Campo input[type=file] para upload de imagens no Gemini",
                    seletores_rapidos=[
                        'input[type="file"]',
                        'input[type="file"][multiple]',
                        'input[accept*="image"]',
                    ],
                    palavras_semanticas=[],  # input[type=file] não tem texto visível
                    permitir_autocura=False,
                    etapa="GEMINI_UPLOAD",
                )
                if el is not None:
                    return el
                
                # Fallback: busca qualquer input file mesmo oculto
                try:
                    self.driver.switch_to.default_content()
                except: pass
                
                try:
                    elementos = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
                    for e in elementos:
                        if e is not None:
                            return e
                except Exception as e:
                    ultimo_erro = e
                
                time.sleep(0.1)
        finally:
            self.driver.implicitly_wait(5)
        
        if ultimo_erro:
            raise ultimo_erro
        raise TimeoutException('Nenhum input[type=file] encontrado no DOM.')

    def _obter_textarea_prompt(self) -> WebElement:
        # 🛡️ HUNTER: Busca via cache/semântica com performance
        el = cacar_elemento_universal(
            driver=self.driver,
            chave_memoria="gemini_textarea_prompt",
            descricao_para_ia="Caixa de digitação de texto (textarea/contenteditable) para enviar prompts no chat do Gemini",
            seletores_rapidos=[
                'rich-textarea div[contenteditable="true"]',
                'div[contenteditable="true"][role="textbox"]',
                '.initial-input-area-container textarea',
                'textarea[placeholder="Ask Gemini"]',
                'div[aria-label*="Message"]',
                'div.editor-container div[contenteditable="true"]',
            ],
            palavras_semanticas=[],  # textarea não tem innerText útil
            permitir_autocura=True,
            driver_acessibilidade=getattr(self, 'driver_acessibilidade', None),
            url_gemini=getattr(self, 'url_gemini_acessibilidade', None),
            etapa="GEMINI_CHAT",
        )
        if el and el.is_displayed() and el.is_enabled():
            return el
        
        # Fallback com timeout estendido (8s)
        fim = time.time() + 8
        while time.time() < fim:
            for seletor in ['rich-textarea div[contenteditable="true"]', 'div[contenteditable="true"][role="textbox"]', 'textarea']:
                try:
                    elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                    for e in elementos:
                        if e.is_displayed() and e.is_enabled():
                            return e
                except: pass
            time.sleep(0.5)
            
        # Se chegou aqui, passou 8 segundos e a caixa não apareceu.
        _log("⚠️ Caixa de digitação sumiu! Chamando trator para tentar recuperar a tela...")
        if self._superar_bloqueios_e_onboarding():
            for seletor in ['rich-textarea div[contenteditable="true"]', 'div[contenteditable="true"][role="textbox"]', 'textarea']:
                try:
                    elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                    for e in elementos:
                        if e.is_displayed() and e.is_enabled():
                            return e
                except: pass
                    
        salvar_print_debug(self.driver,"ERRO_TEXTAREA_MORTA")
        raise TimeoutException('Falha irrecuperável: A caixa de digitação não existe na tela atual.')

    def _obter_botao_enviar(self, permitir_ia: bool = False) -> Optional[WebElement]:
        """Busca direta primeiro (instantâneo), Hunter como fallback com self-healing."""
        # ⚡ CAMINHO RÁPIDO: Seletores diretos (< 1ms)
        _CSS_ENVIAR = (
            'button[aria-label="Send message"], button[aria-label="Enviar mensagem"], '
            'button[data-test-id="send-button"], .send-button-container button'
        )
        try:
            btns = self.driver.find_elements(By.CSS_SELECTOR, _CSS_ENVIAR)
            for b in btns:
                if b.is_displayed() and b.get_attribute('disabled') is None and (b.get_attribute('aria-disabled') or '').strip().lower() != 'true':
                    return b
        except:
            pass
        
        # 🧠 FALLBACK HUNTER: Se Google mudou a interface
        btn = cacar_elemento_universal(
            driver=self.driver,
            chave_memoria="gemini_botao_enviar",
            descricao_para_ia="Botão de enviar mensagem (Send message) no chat do Gemini",
            seletores_rapidos=[
                'button[aria-label="Send message"]', 
                'button[aria-label="Enviar mensagem"]',
                '.send-button-container button', 
                'button[data-test-id="send-button"]'
            ],
            palavras_semanticas=['send message', 'enviar mensagem'],
            permitir_autocura=permitir_ia,
            driver_acessibilidade=self.driver_acessibilidade,
            url_gemini=self.url_gemini_acessibilidade,
            etapa="GEMINI_CHAT"
        )
        
        if btn and btn.is_displayed() and btn.get_attribute('disabled') is None and (btn.get_attribute('aria-disabled') or '').strip().lower() != 'true':
            return btn
            
        return None

    def _aguardar_upload_estabilizar(self, timeout: int = 20, is_video: bool = False) -> None:
        fim = time.time() + timeout
        
        salvar_print_debug(self.driver,f"UPLOAD_AGUARDANDO_INICIO_isvideo_{is_video}")
        
        if is_video:
            _log(f'Aguardando estabilização do upload de VÍDEO (max {timeout}s)...')
            while time.time() < fim:
                try:
                    scroll_ao_fim(self.driver)
                    carregando = False
                    try:
                        # 🛡️ HUNTER: Detecta loaders de upload de vídeo
                        loaders = detectar_com_hunter(
                            driver=self.driver,
                            chave_memoria="gemini_upload_video_loaders",
                            descricao_para_ia="Indicadores de loading/upload de vídeo (progress bar, spinner, uploading) no Gemini",
                            seletores_rapidos=[
                                'mat-progress-bar', '.uploading', '[role="progressbar"]',
                                'mat-spinner', '.loading-spinner',
                                '[aria-label*="loading"]', '[aria-label*="uploading"]',
                            ],
                            palavras_semanticas=["loading", "uploading", "progress", "spinner"],
                            etapa="GEMINI_UPLOAD",
                        )
                        if loaders:
                            carregando = True
                    except Exception:
                        pass
                    
                    if not carregando:
                        btn = self._obter_botao_enviar()
                        if btn is not None:
                            time.sleep(0.5)
                            _log('Upload de vídeo estabilizado e botão de envio habilitado.')
                            salvar_print_debug(self.driver,"UPLOAD_VIDEO_OK")
                            return
                except Exception:
                    pass
                time.sleep(0.5)
        else:
            while time.time() < fim:
                try:
                    scroll_ao_fim(self.driver)
                    btn = self._obter_botao_enviar()
                    if btn is not None:
                        _log('Botão de envio habilitado apos upload.')
                        return
                except Exception:
                    pass
                time.sleep(0.1)
                
        _log('Aviso: upload nao confirmou estado pronto dentro do tempo esperado.')
        salvar_print_debug(self.driver,"UPLOAD_TIMEOUT_AVISO")

    def _texto_limpo(self, txt: str) -> str:
        txt = (txt or '').replace('\r', '\n')
        txt = re.sub(r'\n+', '\n', txt).strip()
        return txt

    def _parece_texto_inutil_ui(self, txt: str) -> bool:
        if not txt:
            return True
        # Normaliza: remove acentos comuns, pontuação, reticências, e faz uppercase
        upper = self._texto_limpo(txt).upper()
        # Remove reticências, pontos, espaços extras
        limpo = re.sub(r'[.\u2026\s]+$', '', upper).strip()  # Remove trailing dots/ellipsis
        limpo = re.sub(r'[*_\-\",:;]', '', limpo).strip()
        
        lixos_exatos = {
            'ANÁLISE', 'ANALISE', 'GEMINI SAID',
            'ANÁLISE\nGEMINI SAID', 'ANALISE\nGEMINI SAID',
            'GEMINI SAID\nANÁLISE', 'GEMINI SAID\nANALISE',
            'SHOW THINKING', 'HIDE THINKING',
            'PENSANDO', 'ANALISANDO', 'ANALYZING', 'THINKING',
            # Toolbar e navegação do Gemini
            'TOOLS', 'TOOLS TOOLS', 'PRO', 'ULTRA', 'WORK',
            'CREATE IMAGE', 'CREATE MUSIC', 'WRITE ANYTHING',
            'BOOST MY DAY', 'HELP ME LEARN',
            'ENTER A PROMPT FOR GEMINI', 'ENTER A PROMPT',
            'INSIRA UMA INSTRUÇÃO',
        }
        if limpo in lixos_exatos or upper in lixos_exatos:
            return True
        linhas = [x.strip() for x in limpo.split('\n') if x.strip()]
        palavras_lixo = {'ANÁLISE', 'ANALISE', 'GEMINI SAID', 'SHOW THINKING', 
                         'HIDE THINKING', 'PENSANDO', 'ANALISANDO', 'ANALYZING', 'THINKING',
                         'O GEMINI DISSE', 'GEMINI DISSE',
                         'TOOLS', 'PRO', 'ULTRA', 'WORK', '+',
                         'CREATE IMAGE', 'CREATE MUSIC', 'WRITE ANYTHING',
                         'BOOST MY DAY', 'HELP ME LEARN'}
        if linhas and all(l in palavras_lixo for l in linhas):
            return True
        # 🛡️ Padrões parciais: texto que COMEÇA com lixo UI e é muito curto (< 50 chars)
        prefixos_lixo = ['ANALISE', 'ANÁLISE', 'PENSANDO', 'ANALISANDO', 'THINKING', 'ANALYZING',
                         'TOOLS', 'CREATE', 'ENTER A PROMPT', 'INSIRA']
        if len(limpo) < 50 and any(limpo.startswith(p) for p in prefixos_lixo):
            return True
        return False

    def _gemini_esta_processando(self) -> bool:
        try:
            mics = self.driver.find_elements(By.CSS_SELECTOR, 'button.speech_dictation_mic_button, button[aria-label="Microphone"]')
            if not mics:
                return True
            for mic in mics:
                if mic.is_displayed():
                    return False
            return True
        except StaleElementReferenceException:
            return True
        except Exception:
            return False

    def _contar_model_responses(self) -> int:
        """Conta quantas model-response existem no DOM neste momento."""
        try:
            return self.driver.execute_script("""
                var respostas = document.querySelectorAll('model-response, response-message, [data-message-author="model"], [data-author-role="model"], .model-message');
                return respostas.length;
            """) or 0
        except Exception:
            return 0

    def _extrair_texto_resposta_recente(self, indice_esperado: int = -1) -> str:
        """Blindada Suprema v2: Extrai texto da resposta do Gemini com 3 camadas de fallback.
        
        Método 1: JavaScript com seletores ampliados (custom elements + classes modernas)
        Método 2: CSS selectors tradicionais (legado)
        Método 3: NUCLEAR — traversal bruto do DOM + document.body.innerText
        
        Args:
            indice_esperado: Índice (0-based) da model-response que queremos ler.
                             Se -1, usa a última (comportamento legado).
        """
        salvar_print_debug(self.driver,"EXTRAINDO_TEXTO_PROCURANDO")
        
        def _limpar_ruido_ui(txt: str) -> str:
            """Remove lixo de UI comum grudado no texto extraído."""
            ruidos_ui = [
                "show thinking", "hide thinking", "gemini said", "gemini disse",
                "thumb_up", "thumb_down", "content_copy", "refresh",
                "more_vert", "share", "volume_up", "good response", "bad response",
                "edit", "retry", "copy code", "use code", "run", "play_arrow",
                "is thinking", "carregando", "loading"
            ]
            for ruido in ruidos_ui:
                txt = re.sub(re.escape(ruido), '', txt, flags=re.IGNORECASE)
            return ' '.join(txt.split()).strip()
        
        def _texto_valido(txt: str) -> bool:
            """Retorna True se o texto parece ser uma resposta real (não lixo de UI)."""
            if not txt or len(txt) < 20:
                return False
            return not self._parece_texto_inutil_ui(txt)
        
        # =====================================================================
        # ⚡ MÉTODO 0: body.innerText direto — SEMPRE funciona, ignora DOM
        # Se o texto do body contém JSON ou blocos substanciais após o prompt,
        # captura imediatamente sem depender de NENHUM seletor CSS/JS.
        # =====================================================================
        try:
            body_raw = self.driver.execute_script("return document.body.innerText || '';") or ""
            if body_raw and len(body_raw) > 80:
                # Tenta achar JSON de classificação direto no body
                match_json = re.search(
                    r'\{[^{}]{20,}(?:arquivo_produto|nome_produto|preco|tipo_arquivo|beneficio)[^{}]*\}',
                    body_raw, re.DOTALL | re.IGNORECASE
                )
                if match_json:
                    txt = match_json.group(0).strip()
                    if _texto_valido(txt) and len(txt) > 20:
                        salvar_print_debug(self.driver, "EXTRAINDO_TEXTO_SUCESSO_M0_JSON")
                        _log(f"✅ JSON capturado via Método 0/body.innerText ({len(txt)} chars)")
                        return txt
                
                # Tenta achar um bloco JSON completo (com array ou objeto aninhado)
                match_json_full = re.search(r'\{[\s\S]{30,3000}\}', body_raw)
                if match_json_full:
                    candidate = match_json_full.group(0).strip()
                    try:
                        import json
                        json.loads(candidate)
                        # É JSON válido!
                        txt = _limpar_ruido_ui(self._texto_limpo(candidate))
                        if _texto_valido(txt) and len(txt) > 20:
                            salvar_print_debug(self.driver, "EXTRAINDO_TEXTO_SUCESSO_M0_JSONVALID")
                            _log(f"✅ JSON válido capturado via Método 0 ({len(txt)} chars)")
                            return txt
                    except (json.JSONDecodeError, ValueError):
                        pass
                
                # Separa prompt do user vs resposta do model via marcadores conhecidos
                # NÃO usar 'Tools' — é toolbar genérica e pega lixo do input box
                separadores = ['Responda apenas: OK', 'Retorne EXCLUSIVAMENTE', 'Enter a prompt for Gemini',
                               'Insira uma', 'Enter a prompt']
                for sep in separadores:
                    idx = body_raw.rfind(sep)
                    if idx > 0:
                        after = body_raw[idx + len(sep):].strip()
                        # Remove linhas de UI (Create image, Write anything, etc.)
                        linhas = [l.strip() for l in after.split('\n') if l.strip()]
                        linhas_limpas = [l for l in linhas if len(l) > 3 and l not in [
                            'Create image', 'Create music', 'Write anything', 'Boost my day',
                            'Help me learn', 'Pro', 'Tools', '+', 'Ultra', 'WORK'
                        ]]
                        if linhas_limpas:
                            texto_resposta = '\n'.join(linhas_limpas).strip()
                            txt = _limpar_ruido_ui(self._texto_limpo(texto_resposta))
                            
                            # 🛡️ Anti-prompt: rejeita se o texto contém assinaturas do PROMPT enviado
                            _assinaturas_prompt = [
                                'devolva apenas', 'retorne exclusivamente', 'responda apenas',
                                'diretriz final', 'não use blocos de código',
                                'nao use blocos', 'json puro', 'sistema calibrado',
                                'arquivo_produto', 'preco_detectado',  # campos que aparecem no prompt de instrução
                            ]
                            _txt_lower = txt.lower()
                            if any(sig in _txt_lower for sig in _assinaturas_prompt):
                                _log(f"⚠️ Método 0/split capturou texto do PROMPT (não resposta). Descartando...")
                                break
                            
                            if _texto_valido(txt) and len(txt) > 15:
                                salvar_print_debug(self.driver, "EXTRAINDO_TEXTO_SUCESSO_M0_SPLIT")
                                _log(f"✅ Texto capturado via Método 0/split ({len(txt)} chars): {txt[:80]}...")
                                return txt
                        break
        except Exception as e_m0:
            _log(f"⚠️ Método 0 falhou: {str(e_m0)[:60]}")
        
        # =====================================================================
        # 🎯 MÉTODO 1: JavaScript com seletores AMPLIADOS + Shadow DOM piercing
        # =====================================================================
        try:
            texto_js = self.driver.execute_script("""
                var indiceAlvo = arguments[0];
                
                // === FASE 1: Seletores conhecidos (antigo + novo Gemini) ===
                // ORDEM IMPORTA: mais específicos primeiro, genéricos por último
                var seletoresResposta = [
                    'model-response',
                    'response-message', 
                    '[data-message-author="model"]',
                    '[data-author-role="model"]',
                    '.model-message',
                    '.response-container',
                    '.model-response-text',
                    'div[data-content-type="response"]',
                    // Seletores semi-genéricos (CUIDADO: podem pegar toolbar)
                    '.conversation-turn',
                    'div[class*="response-container"]',
                    'div[class*="answer"]',
                    'div[class*="assistant"]',
                ];
                
                var respostas = [];
                for (var i = 0; i < seletoresResposta.length; i++) {
                    try {
                        var found = document.querySelectorAll(seletoresResposta[i]);
                        if (found.length > 0) {
                            respostas = found;
                            break;
                        }
                    } catch(e) {}
                }
                
                // === FASE 2: Fallback — message-content genérico ===
                if (!respostas.length) {
                    var msgFallbacks = [
                        '.message-content', 
                        'message-content',
                        '[class*="message-content"]',
                        '[class*="markdown"]',
                        '.markdown-content',
                        'div.markdown'
                    ];
                    for (var j = 0; j < msgFallbacks.length; j++) {
                        try {
                            var msgs = document.querySelectorAll(msgFallbacks[j]);
                            if (msgs.length > 0) {
                                var ultimo = msgs[msgs.length - 1];
                                var t = (ultimo.innerText || ultimo.textContent || '').trim();
                                if (t.length > 20) return t;
                            }
                        } catch(e) {}
                    }
                }
                
                // === FASE 3: Shadow DOM piercing ===
                if (!respostas.length) {
                    var allElements = document.querySelectorAll('*');
                    for (var k = 0; k < allElements.length; k++) {
                        var el = allElements[k];
                        if (el.shadowRoot) {
                            try {
                                var shadowResps = el.shadowRoot.querySelectorAll(
                                    'model-response, [data-message-author="model"], .response-container, [class*="message-content"], .markdown'
                                );
                                if (shadowResps.length > 0) {
                                    respostas = shadowResps;
                                    break;
                                }
                            } catch(e) {}
                        }
                    }
                }
                
                if (!respostas.length) return '';
                
                // Seleciona a resposta pelo índice
                var alvo;
                if (indiceAlvo >= 0 && indiceAlvo < respostas.length) {
                    alvo = respostas[indiceAlvo];
                } else {
                    alvo = respostas[respostas.length - 1];
                }
                
                // Tenta extrair o texto da resposta
                var textoFinal = '';
                
                // Seletores internos para o conteúdo de texto
                var seletoresTexto = [
                    '.model-response-text',
                    'message-content .markdown',
                    '.markdown-content',
                    '.markdown',
                    '.content',
                    '.text',
                    '[class*="response-text"]',
                    '[class*="markdown"]',
                    'p, pre, code, li'
                ];
                
                for (var m = 0; m < seletoresTexto.length; m++) {
                    try {
                        var textBlocks = alvo.querySelectorAll(seletoresTexto[m]);
                        if (textBlocks.length > 0) {
                            var partes = [];
                            for (var n = 0; n < textBlocks.length; n++) {
                                var tb = textBlocks[n];
                                if (tb.offsetParent !== null || tb.getBoundingClientRect().height > 0) {
                                    var t = (tb.innerText || tb.textContent || '').trim();
                                    if (t.length > 2) partes.push(t);
                                }
                            }
                            if (partes.length > 0) {
                                textoFinal = partes.join('\\n');
                                break;
                            }
                        }
                    } catch(e) {}
                }
                
                // Se nenhum seletor interno funcionou, pega o innerText do container inteiro
                if (!textoFinal.trim()) {
                    textoFinal = (alvo.innerText || alvo.textContent || '').trim();
                }
                
                // 🛡️ Guard final no JS: rejeita lixo de toolbar (< 20 chars)
                if (textoFinal.length < 20) return '';
                
                return textoFinal;
            """, indice_esperado)
            
            if texto_js:
                txt = _limpar_ruido_ui(self._texto_limpo(texto_js))
                if _texto_valido(txt):
                    salvar_print_debug(self.driver,"EXTRAINDO_TEXTO_SUCESSO_M1")
                    _log(f"✅ Texto capturado via Método 1 ({len(txt)} chars): {txt[:80]}...")
                    return txt
        except Exception as e_m1:
            _log(f"⚠️ Método 1 falhou: {str(e_m1)[:60]}")
        
        # =====================================================================
        # 🔄 MÉTODO 2: Seletores CSS tradicionais (fallback legado)
        # =====================================================================
        seletores = [
            'model-response .model-response-text',
            'model-response message-content',
            'model-response',
            '[data-message-author="model"]',
            '[data-author-role="model"]',
            '.model-message',
            '.message-content',
            'div[data-test-id="model-response"]',
            # Seletores modernos adicionados
            'div[class*="response-container"]',
            'div[class*="model-response"]',
            'div[class*="assistant-message"]',
            'div[class*="bot-message"]',
            '.conversation-turn:last-child',
        ]
        
        for seletor in seletores:
            try:
                elementos = self.driver.find_elements(By.CSS_SELECTOR, seletor)
                if not elementos: 
                    continue
                
                # 🎯 Usa índice específico se disponível, senão último
                if indice_esperado >= 0 and indice_esperado < len(elementos):
                    el = elementos[indice_esperado]
                else:
                    el = elementos[-1]
                
                txt_bruto = self.driver.execute_script(
                    "return arguments[0].innerText || arguments[0].textContent || '';", el
                )
                txt = _limpar_ruido_ui(self._texto_limpo(txt_bruto or ''))
                
                if _texto_valido(txt):
                    salvar_print_debug(self.driver,"EXTRAINDO_TEXTO_SUCESSO_M2")
                    _log(f"✅ Texto capturado via Método 2 seletor='{seletor}' ({len(txt)} chars)")
                    return txt
            except Exception:
                pass
        
        # =====================================================================
        # 💣 MÉTODO 3: NUCLEAR — Traversal bruto do DOM inteiro
        # =====================================================================
        _log("⚠️ Métodos 1 e 2 falharam. Ativando extração NUCLEAR (Método 3)...")
        
        # --- 3A: Busca blocos de texto grandes perto do final da página ---
        try:
            texto_nuclear = self.driver.execute_script("""
                // Estratégia: Varre TODOS os elementos do DOM e pega o maior bloco
                // de texto que esteja na metade inferior da página (onde a resposta vive)
                var pageHeight = document.documentElement.scrollHeight || document.body.scrollHeight;
                var threshold = pageHeight * 0.3; // Ignora os primeiros 30% da página
                
                var melhorTexto = '';
                var melhorTamanho = 0;
                
                // Seletores genéricos que qualquer app Angular/React/Web usaria para conteúdo
                var candidatos = document.querySelectorAll('div, section, article, main, p, pre');
                
                for (var i = 0; i < candidatos.length; i++) {
                    var el = candidatos[i];
                    try {
                        var rect = el.getBoundingClientRect();
                        var posAbsoluta = rect.top + window.scrollY;
                        
                        // Ignora elementos pequenos, invisíveis, ou no topo da página
                        if (rect.height < 30 || rect.width < 100) continue;
                        if (posAbsoluta < threshold) continue;
                        if (el.offsetParent === null && el.tagName !== 'BODY') continue;
                        
                        // Pega só o texto direto (sem filhos para evitar duplicação)
                        var texto = (el.innerText || '').trim();
                        
                        // O texto precisa ser substancial e parecer uma resposta
                        if (texto.length > 50 && texto.length > melhorTamanho) {
                            // Filtra containers que são apenas wrapper (texto = soma dos filhos)
                            var filhosTexto = 0;
                            for (var c = 0; c < el.children.length; c++) {
                                var ft = (el.children[c].innerText || '').trim();
                                if (ft.length > texto.length * 0.9) {
                                    filhosTexto++;
                                }
                            }
                            // Se nenhum filho único tem >90% do texto, este é um bom candidato
                            if (filhosTexto === 0 || el.children.length <= 3) {
                                melhorTexto = texto;
                                melhorTamanho = texto.length;
                            }
                        }
                    } catch(e) {}
                }
                
                return melhorTexto;
            """)
            
            if texto_nuclear:
                txt = _limpar_ruido_ui(self._texto_limpo(texto_nuclear))
                if _texto_valido(txt) and len(txt) > 20:
                    salvar_print_debug(self.driver,"EXTRAINDO_TEXTO_SUCESSO_M3A")
                    _log(f"✅ Texto capturado via Método 3A/Nuclear ({len(txt)} chars): {txt[:80]}...")
                    return txt
        except Exception as e_3a:
            _log(f"⚠️ Método 3A falhou: {str(e_3a)[:60]}")
        
        # --- 3B: Último recurso — document.body.innerText e split pelo prompt ---
        try:
            body_text = self.driver.execute_script("return document.body.innerText || '';") or ""
            if body_text and len(body_text) > 100:
                # Tenta isolar a resposta do modelo procurando por padrões conhecidos
                # O prompt de classificação pede JSON, então procuramos por { ... }
                match_json = re.search(r'\{[^{}]*"(?:arquivo_produto|nome_produto|preco)[^{}]*\}', body_text, re.DOTALL | re.IGNORECASE)
                if match_json:
                    txt = match_json.group(0).strip()
                    salvar_print_debug(self.driver,"EXTRAINDO_TEXTO_SUCESSO_M3B_JSON")
                    _log(f"✅ JSON extraído via Método 3B/body.innerText ({len(txt)} chars)")
                    return txt
                
                # Fallback: pega a última metade do texto da página (a resposta está no final)
                linhas = body_text.split('\n')
                metade = len(linhas) // 2
                texto_fim = '\n'.join(linhas[metade:]).strip()
                txt = _limpar_ruido_ui(self._texto_limpo(texto_fim))
                if _texto_valido(txt) and len(txt) > 30:
                    salvar_print_debug(self.driver,"EXTRAINDO_TEXTO_SUCESSO_M3B_BODY")
                    _log(f"✅ Texto extraído via Método 3B/body ({len(txt)} chars): {txt[:80]}...")
                    return txt
        except Exception as e_3b:
            _log(f"⚠️ Método 3B falhou: {str(e_3b)[:60]}")
        
        # =====================================================================
        # 🚨 DIAGNÓSTICO FINAL: Tudo falhou — captura máxima de info para debug
        # =====================================================================
        try:
            qtd_responses = self.driver.execute_script("""
                var seletores = ['model-response', 'response-message', '[data-message-author="model"]', 
                                 '[data-author-role="model"]', '.model-message', 'message-content',
                                 '.response-container', '.model-response-text',
                                 '[data-message-id]', '.conversation-turn', 'div[class*="response"]',
                                 'div[class*="message"]', 'div[class*="markdown"]'];
                var resultado = {};
                seletores.forEach(function(sel) {
                    try { resultado[sel] = document.querySelectorAll(sel).length; } catch(e) { resultado[sel] = -1; }
                });
                // Adiciona info sobre shadow DOMs
                var shadowCount = 0;
                document.querySelectorAll('*').forEach(function(el) { if (el.shadowRoot) shadowCount++; });
                resultado['_shadow_hosts'] = shadowCount;
                resultado['_body_text_len'] = (document.body.innerText || '').length;
                resultado['_url'] = window.location.href;
                return JSON.stringify(resultado);
            """)
            _log(f"🚨 DIAGNÓSTICO DOM COMPLETO: {qtd_responses}")
        except Exception as e_diag:
            _log(f"⚠️ Erro no diagnóstico DOM: {str(e_diag)[:80]}")
        
        salvar_print_debug(self.driver,"EXTRAINDO_TEXTO_FALHA_TOTAL")
        return ''

    def _interpretar_resposta_binaria(self, texto: str) -> Optional[bool]:
        if not texto:
            return None
        up = self._texto_limpo(texto).upper()
        up_clean = re.sub(r'[*_.\-",:;]', ' ', up)
        
        sim_matches = list(re.finditer(r'\bSIM\b', up_clean))
        nao_matches = list(re.finditer(r'\b(NAO|NÃO)\b', up_clean))
        
        last_sim = sim_matches[-1].start() if sim_matches else -1
        last_nao = nao_matches[-1].start() if nao_matches else -1
        
        if last_sim > last_nao:
            return True
        elif last_nao > last_sim:
            return False
            
        return None

    def _aguardar_fim_analise(self, timeout: int = 120) -> bool:
        """
        Lógica baseada puramente no estado dos botões (Stop vs Mic/Send).
        Identifica quando o processamento terminou validando o sumiço do Stop
        e o reaparecimento do Microfone ou Seta de Envio.
        """
        _log(f'Gemini processando... Monitorando botões (Timeout: {timeout}s).')
        salvar_print_debug(self.driver,"AGUARDANDO_ANALISE_INICIO")
        fim = time.time() + timeout
        
        # ⚡ POLL RÁPIDO: Aguarda o Angular renderizar o botão Stop (em vez de sleep(5) cego)
        _CSS_STOP_RAPIDO = 'button[aria-label="Stop response"], button[aria-label="Parar resposta"], button[aria-label*="Stop"]'
        deadline_stop = time.time() + 5.0
        while time.time() < deadline_stop:
            try:
                stops = self.driver.find_elements(By.CSS_SELECTOR, _CSS_STOP_RAPIDO)
                if any(s.is_displayed() for s in stops):
                    break  # ⚡ Stop apareceu! Pula direto pro monitoramento
            except:
                pass
            time.sleep(0.2)  # Poll a cada 200ms (25x mais rápido que sleep(5))
        
        # 🛡️ SELETORES CONHECIDOS (rápidos, sem cache - botões que MUTAM no DOM)
        _CSS_STOP = 'button[aria-label="Stop response"], button[aria-label="Parar resposta"], button[aria-label*="Stop"]'
        _CSS_IDLE = (
            'button[aria-label*="Microphone"], button[aria-label*="Microfone"], '
            'button[aria-label*="Send message"], button[aria-label*="Enviar mensagem"], '
            'button.speech_dictation_mic_button'
        )
        _CSS_LOADERS = 'mat-progress-bar, .uploading, [role="progressbar"]'
        
        # Flag para fallback Hunter (só aciona se os seletores diretos falharem MUITAS vezes)
        falhas_diretas = 0
        
        while time.time() < fim:
            try:
                # === 1. DETECTA STOP (seletor direto = instantâneo) ===
                botoes_stop = self.driver.find_elements(By.CSS_SELECTOR, _CSS_STOP)
                stop_visivel = any(b.is_displayed() for b in botoes_stop) if botoes_stop else False
                
                if stop_visivel:
                    falhas_diretas = 0  # Reset - os seletores funcionam
                    pass  # IA ainda gerando...
                else:
                    # === 2. DETECTA IDLE (seletor direto) ===
                    botoes_ociosos = self.driver.find_elements(By.CSS_SELECTOR, _CSS_IDLE)
                    idle_visivel = any(b.is_displayed() for b in botoes_ociosos) if botoes_ociosos else False
                    
                    if idle_visivel:
                        falhas_diretas = 0
                        # 3. Confirma sem spinners
                        loaders = self.driver.find_elements(By.CSS_SELECTOR, _CSS_LOADERS)
                        loader_ativo = any(l.is_displayed() for l in loaders) if loaders else False
                        
                        if not loader_ativo:
                            _log("Gatilho detectado: Botão Stop sumiu e interface voltou a ficar ociosa. Geração concluída!")
                            time.sleep(1.0)
                            salvar_print_debug(self.driver,"AGUARDANDO_ANALISE_SUCESSO")
                            return True
                    else:
                        falhas_diretas += 1
                
                # === SELF-HEALING: Se os seletores diretos não acham NADA por 15 ciclos ===
                # Significa que o Google mudou a interface e precisamos reaprender
                if falhas_diretas >= 15:
                    _log("🧠 [SELF-HEALING] Seletores diretos falharam 15x. Ativando Hunter para reaprender interface...")
                    falhas_diretas = 0  # Reset para não spammar
                    
                    # Hunter SEM cache (permitir_autocura=False) para não envenenar com botões mutáveis
                    el_stop = cacar_elemento_universal(
                        driver=self.driver,
                        chave_memoria="_temp_stop_nao_cachear",
                        descricao_para_ia="Botão de parar/stop a geração de resposta no Gemini",
                        seletores_rapidos=['button.stop', 'button[aria-label*="top"]'],
                        palavras_semanticas=["stop", "parar"],
                        permitir_autocura=False,
                        etapa="GEMINI_CHAT"
                    )
                    if el_stop and el_stop.is_displayed():
                        # Aprende o novo seletor para Log (não cacheia)
                        label = el_stop.get_attribute('aria-label') or 'desconhecido'
                        _log(f"🧠 [SELF-HEALING] Stop reaprendido: aria-label='{label}'")
                        continue  # Continua monitorando
                    
                    el_idle = cacar_elemento_universal(
                        driver=self.driver,
                        chave_memoria="_temp_idle_nao_cachear",
                        descricao_para_ia="Botão de microfone ou enviar mensagem quando a IA terminou de responder",
                        seletores_rapidos=['button[aria-label*="icro"]', 'button[aria-label*="end"]'],
                        palavras_semanticas=["microphone", "microfone", "send", "enviar"],
                        permitir_autocura=False,
                        etapa="GEMINI_CHAT"
                    )
                    if el_idle and el_idle.is_displayed():
                        label = el_idle.get_attribute('aria-label') or 'desconhecido'
                        _log(f"🧠 [SELF-HEALING] Idle reaprendido: aria-label='{label}'. Geração concluída!")
                        time.sleep(1.0)
                        return True
                            
            except StaleElementReferenceException:
                pass
            except Exception:
                pass
                
            time.sleep(0.5)
            
        # --- 📸 O PONTO CHAVE: PRINT ANTES DE MORRER ---
        _log(f'Aviso: Timeout de {timeout}s atingido aguardando mudança nos botões.')
        
        # Tira o print no último segundo possível para vermos se o Stop ainda estava lá
        salvar_print_debug(self.driver, "DETALHE_ESTADO_TELA_NA_FALHA")
        
        return False
    
    def _aguardar_resposta_textual(self, timeout: int = 120, indice_resposta: int = -1) -> str:
        # A espera padrão (que pode dar timeout cego se o seletor oculto do Google mudar)
        finalizou = self._aguardar_fim_analise(timeout=timeout)
        
        # =========================================================================
        # 🛡️ INTERVENÇÃO DO HUNTER (SELF-HEALING) ANTES DO REFRESH
        # =========================================================================
        if not finalizou:
            _log("⚠️ Timeout na espera padrão. Acionando Hunter para verificar falso-positivo...")
            
            # Tenta achar o botão de enviar ou o campo de texto (indicadores de que o Gemini parou de escrever)
            # Usa os atributos de acessibilidade da classe caso existam
            driver_med = getattr(self, 'driver_acessibilidade', None)
            url_med = getattr(self, 'url_gemini_acessibilidade', None)
            
            ui_ociosa = cacar_elemento_universal(
                driver=self.driver,
                chave_memoria="gemini_ui_ociosa",
                descricao_para_ia="Input de texto ou botão de envio de prompt que fica habilitado quando a IA termina de responder",
                seletores_rapidos=["//button[@aria-label='Send message']", "//div[@role='textbox']", "//rich-textarea"],
                palavras_semanticas=["enviar", "send", "digite", "type", "mensagem", "message"],
                permitir_autocura=True,
                driver_acessibilidade=driver_med,
                url_gemini=url_med,
                etapa="GEMINI_MONITORAMENTO"
            )
            
            if ui_ociosa:
                _log("🎯 Hunter confirmou que a UI está livre. Falso timeout detectado e anulado!")
                finalizou = True  # Cancela o F5, a resposta já está lá e pronta pra ser copiada!
            else:
                _log("🚨 Hunter também não encontrou a UI livre. A tela travou de verdade.")
        # =========================================================================

        if not finalizou:
            # 📸 PRINT DE SEGURANÇA ANTES DO REFRESH
            salvar_print_debug(self.driver, "ESTADO_TELA_PRE_RECOVERY")

            _log('⚠️ Timeout confirmado na UI. Forçando F5 Recovery e reinício da etapa...')
            self.driver.refresh()
            time.sleep(1.5) # Tempo para o Chrome estabilizar pós-refresh
            self._superar_bloqueios_e_onboarding()
            
            # Em vez de tentar ler um texto que sumiu, retornamos um sinal de RESET
            return 'RECOVERY_TRIGGERED'
        
        time.sleep(0.5) # Respiro mínimo para o Angular renderizar o texto final
        
        # --- DETECÇÃO DE RESET SILENCIOSO DO GEMINI ---
        # Se a página resetou (voltou ao estado 'Where should we start'), não há resposta
        try:
            page_text = self.driver.page_source[:3000].lower()
            sinais_reset = ['where should we start', 'como posso ajudar', 'enter a prompt for gemini']
            tem_resposta = bool(self.driver.find_elements('css selector', 'message-content, .response-container, .model-response-text, div[data-message-author-role="model"]'))
            if any(s in page_text for s in sinais_reset) and not tem_resposta:
                _log("🚨 RESET SILENCIOSO DETECTADO: Gemini resetou o chat sem responder. Cache corrompido.")
                salvar_print_debug(self.driver, "GEMINI_SILENT_RESET")
                return 'SILENT_RESET'
        except Exception:
            pass
        
        # --- POLLING INTELIGENTE ---
        _log("Iniciando captura dinâmica de texto (Polling)...")
        fim = time.time() + 15.0  # Aumentado de 10s para 15s
        
        # 🎯 RESOLUÇÃO DO ÍNDICE: Se temos indice_resposta, aguarda a model-response aparecer
        _idx_alvo = indice_resposta
        if _idx_alvo >= 0:
            _deadline_idx = time.time() + 10.0
            while time.time() < _deadline_idx:
                _qtd_atual = self._contar_model_responses()
                if _qtd_atual > _idx_alvo:
                    break  # A resposta no índice esperado já existe no DOM
                time.sleep(0.5)
        
        while time.time() < fim:
            try:
                scroll_ao_fim(self.driver)
                texto = self._extrair_texto_resposta_recente(indice_esperado=_idx_alvo)
                if texto:
                    # 🛡️ GUARD DE QUALIDADE: Filtra lixo de UI ("Análise...", "Pensando...")
                    if self._parece_texto_inutil_ui(texto):
                        _log(f"⚠️ Texto capturado é lixo de UI ({len(texto)} chars: '{texto[:30]}'). Esperando resposta real...")
                        time.sleep(1.0)
                        continue
                    _log(f"✅ Texto capturado com sucesso.")
                    return texto
            except Exception:
                pass
            time.sleep(0.5)
            
        # Última tentativa: pega o que tiver, mesmo que curto
        try:
            texto_final = self._extrair_texto_resposta_recente(indice_esperado=_idx_alvo)
            if texto_final and len(texto_final) > 2:
                _log(f"⚠️ Texto capturado no limite ({len(texto_final)} chars). Usando mesmo assim.")
                return texto_final
        except: pass
            
        return 'SEM_RESPOSTA_UTIL'
    
    def anexar_arquivo_local(self, caminho: Path) -> None:
        caminho = Path(caminho)
        if not caminho.exists():
            raise FileNotFoundError(f'Arquivo nao encontrado: {caminho}')
        _log(f'Anexando arquivo: {caminho.name}')
        
        # 1. Chamar apenas se NÃO for headless (otimização de 0.5s)
        is_headless = self.driver.capabilities.get('moz:headless') or 'headless' in str(self.driver.capabilities).lower()
        if not is_headless:
            from integrations.utils import forcar_fechamento_janela_windows
            forcar_fechamento_janela_windows()

        try:
            scroll_ao_fim(self.driver)

            # 🚨 Desliga espera implícita para buscas relâmpago não bloquearem
            self.driver.implicitly_wait(0)
            try:
                # 🛡️ PROTOCOLO HUNTER: Mapeia quantos arquivos já existem antes de começar
                xpath_remover = "//button[contains(@aria-label, 'Remover') or contains(@aria-label, 'Remove')]"
                qtd_antes = len(self.driver.find_elements(By.XPATH, xpath_remover))

                # --- TENTATIVA DE INPUT DIRETO (ULTRA RÁPIDA) ---
                input_file = None
                try:
                    # ⚡ BUSCA RELÂMPAGO: Se o Gemini já deixou o input no DOM (comum em uploads subsequentes)
                    inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
                    for inp in inputs:
                        if inp is not None:
                            input_file = inp
                            break
                except:
                    pass
            finally:
                self.driver.implicitly_wait(5)

            if not input_file:
                # --- CAMINHO COMPLETO: Precisa abrir o menu de upload ---
                
                # 1. ACHAR O BOTÃO "+" (com cache do Hunter)
                seletores_mais = [
                    'button[aria-controls="upload-file-menu"]',
                    'button[aria-label*="envio de arquivo"]', 
                    'button[aria-label*="upload file menu"]',
                    'button[aria-label*="Open upload"]',
                    'button[aria-label*="Fazer upload"]',
                    'button[aria-label*="Anexar"]',
                    'mat-icon[fonticon="add_2"]/ancestor::button',
                    'button.upload-card-button',
                    'button[jslog*="188896"]',
                    'button[jslog*="188890"]',
                ]
                
                btn = cacar_elemento_universal(
                    driver=self.driver,
                    chave_memoria="gemini_btn_mais_anexo",
                    descricao_para_ia="O botão de '+' ao lado da caixa de texto no chat do Gemini, usado para fazer upload de imagens ou anexar arquivos.",
                    seletores_rapidos=seletores_mais,
                    palavras_semanticas=['upload', 'anexar', 'arquivo'],
                    permitir_autocura=True,
                    driver_acessibilidade=getattr(self, 'driver_acessibilidade', None),
                    url_gemini=getattr(self, 'url_gemini_acessibilidade', None),
                    etapa="GEMINI_DIRETOR"
                )

                if btn:
                    try:
                        if btn.is_displayed() and "close" not in (btn.get_attribute("class") or ""):
                            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                            time.sleep(0.1)
                            
                            js_click(self.driver, btn)
                            time.sleep(0.3)
                            
                            # SNIPER DE POPUP DE IMAGEM (só na primeira vez da sessão)
                            if not getattr(self, '_agree_popup_ja_fechado', False):
                                try:
                                    btn_agree = self.driver.find_elements(By.CSS_SELECTOR, 
                                        'button[data-test-id="upload-image-agree-button"]')
                                    if btn_agree and btn_agree[0].is_displayed():
                                        _log("🛡️ Popup de 'Política de Imagens' detectado. Clicando em Agree...")
                                        js_click(self.driver, btn_agree[0])
                                        self._agree_popup_ja_fechado = True
                                        time.sleep(0.5) 
                                        js_click(self.driver, btn)
                                        time.sleep(0.3)
                                except:
                                    pass
                    except: 
                        pass

                # 2. BOTÃO "Enviar arquivo" DENTRO DO MENU (espera curta)
                try:
                    btn_enviar = WebDriverWait(self.driver, 2).until(EC.element_to_be_clickable((
                        By.CSS_SELECTOR, 'button[data-test-id="local-images-files-uploader-button"]'
                    )))
                    js_click(self.driver, btn_enviar)
                    time.sleep(0.3)
                except:
                    pass 

                # 3. AGORA BUSCA O INPUT (deve ter aparecido após os cliques)
                try:
                    inputs = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="file"]')
                    for inp in inputs:
                        if inp is not None:
                            input_file = inp
                            break
                except:
                    pass

            # --- VALIDAÇÃO E INJEÇÃO ---
            if not input_file:
                # 🐌 FALLBACK LENTO: Só usa o loop pesado se tudo acima falhou
                input_file = self._encontrar_input_file_visivel_ou_oculto(timeout=10)
            
            self.driver.execute_script(
                "arguments[0].style.display='block'; arguments[0].style.visibility='visible'; arguments[0].style.opacity=1; arguments[0].style.height='1px'; arguments[0].style.width='1px';",
                input_file,
            )

            input_file.send_keys(str(caminho.resolve()))         
            _log(f'Upload iniciado: {caminho.name}')

            # Limpeza rápida de menus abertos
            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            
            # 🚀 FIRE AND FORGET: Aceleração bruta sem esperar o carregamento visual da barra
            time.sleep(0.1)
            _log(f"✅ Arquivo '{caminho.name}' injetado na fila de upload.")

        except Exception as e:
            _log(f'🛡️ Falha Crítica no Fluxo de Anexo: {str(e).splitlines()[0]}')
            salvar_print_debug(self.driver, f"ERRO_ANEXO_{caminho.stem}")
            raise Exception(f"Timeout ou falha de UI ao anexar {caminho.name}.")
        
    def enviar_prompt(
        self,
        prompt: str,
        timeout: int = 120,
        aguardar_resposta: bool = True,
    ) -> str:
        self._verificar_driver_vivo()
        _log(f'Enviando prompt ({len(prompt)} chars)...')

        # ⚡ COOLDOWN INTELIGENTE: Espera a textarea ficar pronta (em vez de sleep(2.5) cego)
        deadline_cool = time.time() + 3.0
        while time.time() < deadline_cool:
            try:
                ta = self.driver.find_elements(By.CSS_SELECTOR, 'div[contenteditable="true"], rich-textarea div[contenteditable]')
                if ta and ta[0].is_displayed() and ta[0].is_enabled():
                    break
            except: pass
            time.sleep(0.2)

        # 🛡️ ANTI-POPUP: Fecha popups promocionais (Deep Research, etc.) que bloqueiam o textarea
        try:
            # Normaliza removendo VÍRGULAS também (o botão diz "No, thanks" com vírgula)
            _tl = "translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ,', 'abcdefghijklmnopqrstuvwxyz ')"
            popups_dismiss = self.driver.find_elements(By.XPATH,
                f"//button[contains({_tl}, 'no thanks') or "
                f"contains({_tl}, 'no  thanks') or "
                f"contains({_tl}, 'não obrigado') or "
                f"contains({_tl}, 'nao obrigado') or "
                f"contains({_tl}, 'dismiss') or "
                f"contains({_tl}, 'fechar') or "
                f"contains({_tl}, 'maybe later') or "
                f"contains({_tl}, 'talvez depois')]"
            )
            for btn in popups_dismiss:
                if btn.is_displayed():
                    _log(f"🛡️ Popup promocional detectado. Fechando: '{(btn.text or '')[:25]}'")
                    js_click(self.driver, btn)
                    time.sleep(0.5)
                    break
        except: pass

        # 🛡️ ANTI-CANVAS: Remove overlays de discovery/canvas que bloqueiam cliques
        # O Gemini mostra cards como "Canvas feature" que ficam POR CIMA do textarea
        try:
            self.driver.execute_script("""
                // Remove imagens de discovery/canvas que cobrem a textarea
                document.querySelectorAll('img[alt*="Canvas"], img[alt*="canvas"], img[src*="discovery"], img[src*="canvas_discovery"]').forEach(function(el) {
                    el.remove();
                });
                // Remove overlays/backdrops genéricos
                document.querySelectorAll('.cdk-overlay-backdrop, .cdk-overlay-container > :not(:empty), [class*="discovery-card"], [class*="promo-card"]').forEach(function(el) {
                    if (el.getBoundingClientRect().height > 200) {
                        el.style.display = 'none';
                    }
                });
                // ESC para fechar qualquer coisa flutuante
                document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}));
            """)
        except: pass

        salvar_print_debug(self.driver,"PROMPT_PREPARACAO")
        
        # 🎯 SNAPSHOT: Conta quantas model-response existem ANTES de enviar o prompt.
        # A resposta nova será no índice qtd_antes (0-based).
        self._indice_resposta_esperada = self._contar_model_responses()
        
        try:
            scroll_ao_fim(self.driver)
            textarea = self._obter_textarea_prompt()
            
            # 🛡️ Click com fallback JS (evita "element click intercepted" de overlays)
            try:
                textarea.click()
            except Exception as e_click:
                _log(f"⚠️ Click direto interceptado ({str(e_click)[:40]}). Usando JS click...")
                self.driver.execute_script("arguments[0].focus(); arguments[0].click();", textarea)
            time.sleep(0.1)
            
            # 🧹 LIMPA a textarea antes de digitar (evita duplicação de prompt residual)
            try:
                textarea.send_keys(Keys.CONTROL, "a")
                time.sleep(0.05)
                textarea.send_keys(Keys.DELETE)
                time.sleep(0.05)
                # Fallback: limpa via JS se o send_keys não funcionou
                self.driver.execute_script("arguments[0].innerHTML = '';", textarea)
            except: pass
            
            # === SOLUÇÃO DEFINITIVA HEADLESS: Digitação Real Fragmentada ===
            # Sem Pyperclip, sem TrustedHTML. Remove emojis nativamente 
            # e escreve o texto diretamente no input buffer.
            prompt_seguro = re.sub(r'[^\u0000-\uFFFF]', '', prompt)

            salvar_ultimo_prompt(prompt_seguro)
                        
            try:
                # Método blindado Selenium: Aciona a API nativa de eventos do Chrome
                self.driver.execute_script(
                    "arguments[0].focus(); document.execCommand('insertText', false, arguments[1]);",
                    textarea, prompt_seguro
                )
                time.sleep(0.2)
                # Dá um espaço final para despertar os gatilhos do Angular
                textarea.send_keys(" ")
            except Exception as e:
                _log(f'Fallback de fallback ativado para digitação: {e}')
                textarea.send_keys(prompt_seguro)
                
            _log('Prompt digitado')
            salvar_print_debug(self.driver,"PROMPT_DIGITADO")
            
            scroll_ao_fim(self.driver)
            
            botao_submit = None
            fim = time.time() + 5
            while time.time() < fim:
                scroll_ao_fim(self.driver)
                # 🛠️ AJUSTE SELF-HEALING: Tenta obter o botão (na última tentativa do loop, permite IA)
                permitir_ia = (time.time() > fim - 1) 
                botao = self._obter_botao_enviar(permitir_ia=permitir_ia)
                
                if botao is not None:
                    botao_submit = botao
                    break
                time.sleep(0.1)

            if botao_submit is None:
                # Plano de Emergência: Se o botão sumiu de vez, tenta o Enter físico
                _log("⚠️ Botão de envio não localizado. Tentando disparo via tecla ENTER...")
                textarea.send_keys(Keys.ENTER)
                # Definimos como True para tentar validar o esvaziamento abaixo
                botao_submit = textarea 

            # === BLOQUEIO DE CONFIRMAÇÃO DE ENVIO ===
            # Clica no botão e espera até a caixa de texto ESVAZIAR
            tentativas_click = 0
            enviou = False
            
            while tentativas_click < 4 and not enviou:
                try:
                    js_click(self.driver,botao_submit)
                except Exception:
                    try: botao_submit.click()
                    except: pass
                
                # 🛠️ PLANO C: Se for a conta Ultra ou persistir, forçamos o ENTER no textarea
                if tentativas_click > 1:
                    textarea.send_keys(Keys.ENTER)
                
                # Aguarda até 3 segundos para a caixa esvaziar após o clique
                fim_esvaziamento = time.time() + 3
                while time.time() < fim_esvaziamento:
                    try:
                        # Se não conseguir achar a caixa, ou ela estiver vazia, significa que a tela mudou e o envio funcionou!
                        ta = self._obter_textarea_prompt()
                        texto_caixa = self.driver.execute_script("return arguments[0].textContent;", ta) or ""
                        if len(texto_caixa.strip()) < 10:
                            enviou = True
                            break
                    except Exception:
                        enviou = True
                        break
                    time.sleep(0.5)
                
                tentativas_click += 1
            
            if not enviou:
                salvar_print_debug(self.driver,"ERRO_PROMPT_NAO_ENVIADO")
                raise Exception("O botão Submit foi clicado, mas o Gemini ignorou a ação.")
                
            _log('Prompt submetido e processamento iniciado.')
            salvar_print_debug(self.driver,"PROMPT_SUBMETIDO_CLICK")
            
            # --- CHECAGEM PÓS ENVIO ---
            fim_erro = time.time() + 4
            while time.time() < fim_erro:
                try:
                    retry_btns = self.driver.find_elements(By.XPATH, "//span[contains(text(), 'Retry') or contains(text(), 'Tentar novamente')]/ancestor::button")
                    if retry_btns and retry_btns[0].is_displayed():
                        _log("⚠️ Erro de servidor detectado. Clicando em Retry...")
                        js_click(self.driver,retry_btns[0])
                        salvar_print_debug(self.driver,"PROMPT_ERRO_RETRY_APERTADO")
                        break
                    
                    toasts = self.driver.find_elements(By.CSS_SELECTOR, "simple-snack-bar, snack-bar-container, div[class*='snackbar'], div[class*='toast'], [role='alert']")
                    if toasts:
                        for toast in toasts:
                            if toast.is_displayed():
                                t_text = toast.text.lower()
                                if any(word in t_text for word in ["wrong", "errado", "error", "tente", "try again"]):
                                    _log(f"⚠️ Erro na UI detectado ('{t_text[:30]}...'). Dando F5 e abortando...")
                                    salvar_print_debug(self.driver,"PROMPT_ERRO_SNACKBAR_F5")
                                    self.driver.refresh()
                                    time.sleep(3)
                                    return 'ERRO_F5'

                    if self._obter_botao_enviar() is None:
                        break 
                except Exception:
                    pass
                time.sleep(0.2)
            
            scroll_ao_fim(self.driver)
            
            if aguardar_resposta:
                return self._aguardar_resposta_textual(timeout=timeout, indice_resposta=self._indice_resposta_esperada)
            return 'ENVIADO'
            
        except TimeoutException:
            _log('ERRO: Timeout ao enviar prompt. A caixa de texto travou.')
            salvar_print_debug(self.driver,"PROMPT_ERRO_TIMEOUT")
            return 'TIMEOUT'
            
        except Exception as e:
            msg_limpa = str(e).split('\n')[0] # Mata o stacktrace
            _log(f'ERRO ao enviar prompt: {msg_limpa}')
            salvar_print_debug(self.driver,"PROMPT_ERRO_CRITICO")
            return f'ERRO: {msg_limpa}'

    def avaliar_melhor_imagem_base(self, cand_a: Path, cand_b: Path, img_produto: Path, nome_produto: str, estilo: str) -> Path:
        """Faz o upload do Produto Original + Variante A + Variante B e julga a fidelidade."""
        from integrations.utils import _log, salvar_print_debug

        _log(f"Iniciando Teste A/B de Imagens com Validação de Produto: {cand_a.name} vs {cand_b.name}...", "GEMINI-IA")
        self.abrir_novo_chat_limpo()

        self.anexar_arquivo_local(img_produto)
        self.anexar_arquivo_local(cand_a)
        self.anexar_arquivo_local(cand_b)

        prompt_juri = (
            f"Você é um Júri técnico avaliando imagens geradas para anuncio do produto \"{nome_produto}\"."
            f" Recebi 3 imagens nesta ordem:\n"
            f"IMAGEM 1: Produto Original — referencia absoluta de estrutura, formato, cor e detalhes.\n"
            f"IMAGEM 2: Candidata A.\n"
            f"IMAGEM 3: Candidata B.\n\n"

            f"PASSO 1 — ELIMINACAO POR FALHA GRAVE (analise cada candidata separadamente)\n"
            f"Desclassifique imediatamente qualquer candidata que apresentar ao menos UMA das falhas abaixo:\n\n"

            f"FALHAS DE GERACAO (verifica primeiro — eliminacao imediata):\n"
            f"- Candidata identica ou quase identica a Imagem 1 (produto sozinho, sem modelo, sem cenario)\n"
            f"- Candidata sem presenca humana quando o estilo exige modelo ({estilo})\n"
            f"- Candidata que claramente nao foi gerada — parece foto de produto de catalogo ou e-commerce\n\n"

            f"FALHAS DE PRODUTO:\n"
            f"- Produto com estrutura, formato ou cor visivelmente diferentes da Imagem 1\n"
            f"- Pecas ou acessorios inventados que nao existem no produto original\n"
            f"- Produto entortado, fundido ao cenario ou parcialmente ausente\n\n"

            f"FALHAS DE ANATOMIA:\n"
            f"- Maos, bracos ou pernas em excesso ou faltando\n"
            f"- Dedos deformados, fundidos ou em numero errado\n"
            f"- Corpo com proporcoes claramente distorcidas\n\n"

            f"PASSO 2 — DESEMPATE (so se ambas passarem na eliminacao)\n"
            f"Avalie qual candidata tem melhor qualidade de anuncio para o estilo \"{estilo}\":\n"
            f"- Produto em destaque e bem iluminado\n"
            f"- Composicao e enquadramento mais atrativos\n"
            f"- Modelo com postura natural e confiante\n\n"

            f"PASSO 3 — VEREDITO\n"
            f"Se uma candidata foi eliminada no Passo 1, a outra vence automaticamente.\n"
            f"Se ambas forem eliminadas, escolha a menos ruim.\n"
            f"Responda APENAS neste formato exato, sem mais nada:\n"
            f"VENCEDOR: A\n"
            f"ou\n"
            f"VENCEDOR: B"
        )
        resposta_ia = self.enviar_prompt(prompt_juri, timeout=120, aguardar_resposta=True)

        # 📸 Screenshot da decisão do Júri (SEMPRE, independente do resultado)
        salvar_print_debug(self.driver, "JURI_DECISAO_RESPOSTA")
        
        # 🔄 Retry se a resposta não foi útil (novo chat, mesma conta)
        if not resposta_ia or resposta_ia in ('TIMEOUT', 'SEM_RESPOSTA_UTIL', 'RECOVERY_TRIGGERED', 'ERRO_F5', 'SILENT_RESET'):
            _log(f"⚠️ Júri falhou ({resposta_ia}). Reabrindo chat e retentando...", "GEMINI-IA")
            salvar_print_debug(self.driver, "JURI_FALHA_RETRY")
            
            for retry in range(1, 3):
                _log(f"🔄 Retry Júri {retry}/2...", "GEMINI-IA")
                try:
                    self.abrir_novo_chat_limpo()
                    self.anexar_arquivo_local(img_produto)
                    self.anexar_arquivo_local(cand_a)
                    self.anexar_arquivo_local(cand_b)
                    resposta_ia = self.enviar_prompt(prompt_juri, timeout=120, aguardar_resposta=True)
                    salvar_print_debug(self.driver, f"JURI_RETRY{retry}_RESPOSTA")
                    
                    if resposta_ia and resposta_ia not in ('TIMEOUT', 'SEM_RESPOSTA_UTIL', 'RECOVERY_TRIGGERED', 'ERRO_F5', 'SILENT_RESET'):
                        break  # Resposta útil, sai do retry
                except Exception as e_retry:
                    _log(f"⚠️ Retry {retry} falhou: {e_retry}", "GEMINI-IA")

        # Decisão final
        if resposta_ia and "VENCEDOR: B" in resposta_ia.upper():
            _log("Gemini escolheu a Variante B.", "GEMINI-IA")
            return cand_b
        else:
            _log("Gemini escolheu a Variante A (ou fallback).", "GEMINI-IA")
            return cand_a

    def contar_imagens_geradas(self) -> int:
        script_js = """
        const seletores = [
            'model-response:last-of-type img[data-test-id*="generated"]',
            'model-response:last-of-type img[src^="blob:"]',
            'model-response:last-of-type img[alt*="Generated"]',
            'model-response:last-of-type img'
        ];
        let imagensVistas = new Set();
        
        seletores.forEach(seletor => {
            document.querySelectorAll(seletor).forEach(el => {
                const src = (el.src || '').toLowerCase();
                if (src.includes('profile/picture') || src.includes('avatar') || src.includes('logo')) {
                    return;
                }
                if (el.getBoundingClientRect().width > 0) {
                    imagensVistas.add(src);
                }
            });
        });
        
        return imagensVistas.size;
        """
        try:
            total = self.driver.execute_script(script_js)
            return int(total) if total else 0
        except Exception as e:
            return 0

    def aguardar_nova_imagem(self, total_antes: int, timeout: int = 60) -> bool:
        fim = time.time() + timeout
        gemini_ocioso_desde = 0  # Timestamp de quando o Gemini ficou ocioso
        
        while time.time() < fim:
            scroll_ao_fim(self.driver)
            total_agora = self.contar_imagens_geradas()
            if total_agora > total_antes:
                _log(f'Nova imagem detectada: {total_agora} > {total_antes}')
                return True
            
            # 🛡️ EARLY ABORT: Se o Gemini terminou de responder sem gerar imagem,
            # não precisa esperar o timeout inteiro (economiza 30-50s)
            try:
                mic_btns = self.driver.find_elements(By.CSS_SELECTOR, 
                    'button.speech_dictation_mic_button, button[aria-label*="icro"]')
                stop_btns = self.driver.find_elements(By.CSS_SELECTOR,
                    'button[aria-label*="Stop" i], button.stop')
                
                mic_visivel = any(m.is_displayed() for m in mic_btns) if mic_btns else False
                stop_visivel = any(s.is_displayed() for s in stop_btns) if stop_btns else False
                
                if mic_visivel and not stop_visivel:
                    # Gemini está ocioso (mic visível, stop sumiu)
                    if gemini_ocioso_desde == 0:
                        gemini_ocioso_desde = time.time()
                    elif time.time() - gemini_ocioso_desde > 5.0:
                        # 5s consecutivos de ociosidade sem imagem = abortou
                        # Tenta capturar o texto de recusa para diagnóstico
                        try:
                            texto_recusa = self._extrair_texto_resposta_recente()
                            if texto_recusa:
                                _log(f'⚠️ Gemini finalizou SEM imagem. Resposta: "{texto_recusa[:120]}..."')
                            else:
                                _log('⚠️ Gemini finalizou resposta SEM gerar imagem (possível recusa de conteúdo).')
                        except:
                            _log('⚠️ Gemini finalizou resposta SEM gerar imagem (possível recusa de conteúdo).')
                        salvar_print_debug(self.driver, "GEMINI_SEM_IMAGEM_ABORT")
                        return False
                else:
                    gemini_ocioso_desde = 0  # Reset — ainda está processando
            except: pass
            
            time.sleep(0.5) 
        _log('Timeout aguardando nova imagem.')
        salvar_print_debug(self.driver,"ERRO_GERACAO_IMAGEM_TIMEOUT")
        return False

    def baixar_ultima_imagem(self, destino: Path) -> bool:
        destino = Path(destino)
        destino.parent.mkdir(parents=True, exist_ok=True)
        
        # === MEGA-RETRY: 3 tentativas completas do zero ===
        for tentativa_global in range(3):
            try:
                # 🚨 Espera CRÍTICA: dá tempo pro React do Gemini estabilizar
                # Sem isso, qualquer elemento capturado vira "stale" em milissegundos
                time.sleep(2.0)
                
                scroll_ao_fim(self.driver)
                salvar_print_debug(self.driver, "BAIXAR_IMG_INICIO", thread_id=self.thread_id)
                
                # === RE-BUSCA FRESCA da imagem (nunca reusar referência antiga) ===
                candidatos_css = [
                    'button.image-button img',
                    'img.generated-image',
                    'img[src*="googleusercontent"]',
                    'img.image.animate.loaded'
                ]
                
                imgs_validas = []
                for seletor in candidatos_css:
                    try:
                        for img in self.driver.find_elements(By.CSS_SELECTOR, seletor):
                            try:
                                if not img.is_displayed():
                                    continue
                                src = img.get_attribute('src') or ''
                                if 'profile/picture' in src or 'avatar' in src.lower() or 'logo' in src.lower():
                                    continue
                                imgs_validas.append(img)
                            except Exception:
                                continue  # stale individual, pula
                    except Exception:
                        pass

                if not imgs_validas:
                    _log(f'[Tentativa {tentativa_global+1}/3] Nenhuma imagem válida encontrada.')
                    if tentativa_global < 2:
                        time.sleep(2)
                        continue
                    return False
                    
                img_alvo = imgs_validas[-1]

                # === SCROLL com blindagem stale ===
                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center', inline:'nearest'});", img_alvo
                    )
                except Exception:
                    _log(f'[Tentativa {tentativa_global+1}/3] Scroll stale, retentando...')
                    if tentativa_global < 2:
                        continue
                    return False
                
                time.sleep(1.0)
                salvar_print_debug(self.driver, "GEMINI_ANTES_ABRIR_GALERIA", thread_id=self.thread_id)

                # === ABRIR GALERIA com blindagem stale ===
                _log('Tentando abrir galeria...')
                clicado = False
                fim_click = time.time() + 8
                while time.time() < fim_click:
                    scroll_ao_fim(self.driver)
                    try:
                        # Re-busca a imagem a cada tentativa de clique (anti-stale)
                        imgs_fresh = []
                        for sel in candidatos_css:
                            try:
                                imgs_fresh.extend(self.driver.find_elements(By.CSS_SELECTOR, sel))
                            except:
                                pass
                        imgs_fresh_ok = []
                        for im in imgs_fresh:
                            try:
                                if im.is_displayed():
                                    src = im.get_attribute('src') or ''
                                    if 'profile/picture' not in src and 'avatar' not in src.lower():
                                        imgs_fresh_ok.append(im)
                            except:
                                pass
                        if imgs_fresh_ok:
                            img_alvo = imgs_fresh_ok[-1]
                        
                        try:
                            pai = img_alvo.find_element(By.XPATH, "./ancestor::button[contains(@class, 'image-button')]")
                            js_click(self.driver, pai)
                        except:
                            js_click(self.driver, img_alvo)
                            
                        time.sleep(1.0)
                        if self.driver.find_elements(By.CSS_SELECTOR, 
                            'button[aria-label="Baixar imagem no tamanho original"], '
                            'button[data-test-id="download-generated-image-button"]'):
                            clicado = True
                            break
                    except Exception:
                        time.sleep(0.5)
                
                if not clicado:
                    _log(f'[Tentativa {tentativa_global+1}/3] Falha ao abrir galeria.')
                    salvar_print_debug(self.driver, "BAIXAR_IMG_FALHA_GALERIA", thread_id=self.thread_id)
                    if tentativa_global < 2:
                        # ESC pra fechar qualquer overlay parcial
                        try:
                            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                        except:
                            pass
                        time.sleep(1)
                        continue
                    return False

                _log('Imagem gerada clicada. Galeria aberta.')
                salvar_print_debug(self.driver, "GEMINI_GALERIA_ABERTA", thread_id=self.thread_id)
                
                # 🚨 Espera a UI da galeria estabilizar
                time.sleep(2.0)
                
                # === ENCONTRAR BOTÃO DOWNLOAD (busca fresca) ===
                btn_download = None
                seletores_download = [
                    'button[data-test-id="download-generated-image-button"]',
                    'button[aria-label="Baixar imagem no tamanho original"]',
                    'button[aria-label="Download full size image"]',
                ]
                for _ in range(15):
                    # Busca direta via CSS (mais rápido e confiável que Hunter)
                    for sel in seletores_download:
                        try:
                            btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
                            for b in btns:
                                try:
                                    if b.is_displayed():
                                        btn_download = b
                                        break
                                except:
                                    pass
                        except:
                            pass
                        if btn_download:
                            break
                    if btn_download:
                        break
                    time.sleep(0.5)
                    
                if not btn_download:
                    _log('Botão de download não encontrado na interface.')
                    try:
                        btn_fechar = self.driver.find_element(By.CSS_SELECTOR, 'button.arrow-back-button, button[aria-label="Fechar"]')
                        js_click(self.driver, btn_fechar)
                    except:
                        try:
                            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                        except:
                            pass
                    if tentativa_global < 2:
                        continue
                    return False

                # 🚨 CRITICAL FIX: monitorar apenas o diretório DA THREAD ATUAL
                # O CDP (browser.py) redireciona para logs/downloads/thread_X/
                # Mas o botão nativo do Gemini pode ignorar o CDP e salvar em ~/Downloads
                downloads_windows = Path.home() / "Downloads"
                
                # 🛡️ Usa APENAS o diretório da thread atual (evita roubar arquivo de outra thread)
                from integrations.profile_manager import obter_caminho_download_thread
                downloads_thread = obter_caminho_download_thread(self.thread_id).resolve()
                
                dirs_download = [downloads_windows, downloads_thread]
                
                arquivos_antes = set()
                for d in dirs_download:
                    try:
                        arquivos_antes.update(d.glob("*"))
                    except:
                        pass

                salvar_print_debug(self.driver, "GEMINI_ANTES_CLICAR_DOWNLOAD", thread_id=self.thread_id)
                
                # === CLICAR DOWNLOAD com blindagem stale ===
                download_clicado = False
                for tentativa_click in range(3):
                    try:
                        js_click(self.driver, btn_download)
                        _log('Botão nativo de download clicado.')
                        download_clicado = True
                        break
                    except Exception as e:
                        if 'stale' in str(e).lower():
                            _log(f'Botão stale (Tentativa {tentativa_click+1}/3). Refazendo busca...')
                            time.sleep(1)
                            btn_download = None
                            for sel in seletores_download:
                                try:
                                    btns = self.driver.find_elements(By.CSS_SELECTOR, sel)
                                    for b in btns:
                                        try:
                                            if b.is_displayed():
                                                btn_download = b
                                                break
                                        except:
                                            pass
                                except:
                                    pass
                                if btn_download:
                                    break
                            if not btn_download:
                                break
                        else:
                            _log(f'Erro inesperado ao clicar download: {e}')
                            break
                
                if not download_clicado:
                    _log(f'[Tentativa {tentativa_global+1}/3] Não conseguiu clicar no download.')
                    try:
                        ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                    except:
                        pass
                    if tentativa_global < 2:
                        continue
                    return False

                novo_arquivo = None
                fim_down = time.time() + 60 
                while time.time() < fim_down:
                    scroll_ao_fim(self.driver)
                    arquivos_agora = set()
                    for d in dirs_download:
                        try:
                            arquivos_agora.update(d.glob("*"))
                        except:
                            pass
                    novos = arquivos_agora - arquivos_antes
                    
                    novos_concluidos = [f for f in novos if not f.name.endswith('.crdownload') and not f.name.endswith('.tmp')]
                    
                    if novos_concluidos:
                        novo_arquivo = max(novos_concluidos, key=lambda f: f.stat().st_ctime)
                        _log(f'📥 Arquivo detectado: {novo_arquivo.name} em {novo_arquivo.parent}')
                        break
                    time.sleep(0.5)
                    
                # Fecha a galeria
                try:
                    btn_fechar = self.driver.find_element(By.CSS_SELECTOR, 'button.arrow-back-button, button[aria-label="Fechar"]')
                    js_click(self.driver, btn_fechar)
                except:
                    try:
                        ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                    except:
                        pass

                if novo_arquivo:
                    if destino.exists():
                        destino.unlink()
                    shutil.move(str(novo_arquivo), str(destino))
                    _log(f'✅ Imagem baixada em alta resolução e salva em: {destino.name}')
                    return True
                else:
                    _log(f'[Tentativa {tentativa_global+1}/3] Timeout ao aguardar arquivo na pasta Downloads.')
                    salvar_print_debug(self.driver, "BAIXAR_IMG_TIMEOUT_WINDOWS", thread_id=self.thread_id)
                    if tentativa_global < 2:
                        continue
                    return False

            except Exception as e:
                _log(f'ERRO ao baixar imagem (Tentativa {tentativa_global+1}/3): {e}')
                if tentativa_global < 2:
                    time.sleep(2)
                    continue
                return False
        
        return False

    def _listar_candidatos_produto(self, tarefa: Any) -> List[Path]:
        assets = getattr(tarefa, 'candidate_product_assets', None)
        if assets:
            candidatos = [asset.path for asset in assets if getattr(asset, 'is_image', False)]
        else:
            task_assets = getattr(tarefa, 'assets', []) or []
            candidatos = [asset.path for asset in task_assets if getattr(asset, 'is_image', False)]
        candidatos = [p for p in candidatos if p.name.upper() != 'POV_VALIDADO.PNG']
        return candidatos

    def _validar_imagem_produto(
        self,
        caminho_imagem: Path,
        timeout_resposta: int = 60, # Timeout aumentado conforme solicitado
        max_reenvios_prompt: int = 2, # Vai tentar até 3 vezes na mesma conta
    ) -> bool:
        """
        Versão DEFINITIVA: Só reprova (retorna False) se a IA disser explicitamente 'NAO'.
        Qualquer outro erro (Timeout, Vácuo, Bugs) gera um Novo Chat na mesma conta.
        Se esgotar as tentativas na conta, gera uma Exceção para o main.py rodar a conta,
        NUNCA reprovando a imagem injustamente.
        """
        caminho_imagem = Path(caminho_imagem)
        
        # Loop de retentativas na MESMA CONTA (se max_reenvios=2, roda 3 vezes)
        for tentativa_geral in range(1, max_reenvios_prompt + 2):
            _log(f'Validando produto: {caminho_imagem.name} (Tentativa {tentativa_geral}/{max_reenvios_prompt + 1} na mesma conta)...')
            salvar_print_debug(self.driver,f"IA_VALIDACAO_INICIO_T{tentativa_geral}")
            
            try:
                self._forcar_modelo_pro()
                self.anexar_arquivo_local(caminho_imagem)
                
                # ...
                prompt_validacao = PROMPT_VALIDACAO_PRODUTO
                resposta_bruta = self.enviar_prompt(prompt_validacao, timeout=timeout_resposta)
                # ...
                
                # --- TRATAMENTO DE TIMEOUTS E F5 ---
                if resposta_bruta == 'RECOVERY_TRIGGERED':
                    _log("🔄 A interface travou (Timeout). Abrindo um NOVO CHAT na mesma conta para re-tentar...")
                    self.abrir_novo_chat_limpo()
                    continue # Volta para o topo do FOR e tenta de novo do zero na mesma conta
                
                resposta = resposta_bruta.strip().upper()
                _log(f"🕵️ Resposta da IA: '{resposta}'")
                salvar_print_debug(self.driver,f"RESPOSTA_DA_IA_{resposta}")

                # Se a resposta for um erro de leitura conhecido, tenta recuperar com novo chat
                if resposta in ('TIMEOUT', 'TIMEOUT_ANALISE', 'SEM_RESPOSTA_UTIL', 'ERRO_F5', 'SILENT_RESET'):
                    _log(f"⚠️ Falha de leitura ({resposta}). Abrindo NOVO CHAT na mesma conta...")
                    self.abrir_novo_chat_limpo()
                    continue

                # --- O VEREDICTO REAL (O SEGREDO ESTÁ AQUI) ---
                
                # 1. A IA aprovou?
                if 'SIM' in resposta or resposta.startswith('SIM'):
                    return True
                
                # 2. A IA reprovou EXPLICITAMENTE? (Único cenário onde retorna False)
                if 'NAO' in resposta or 'NÃO' in resposta or resposta.startswith('NAO'):
                    return False
                    
                # 3. Respondeu alguma loucura que não é nem SIM nem NAO
                _log(f"⚠️ A IA respondeu fora do padrão. Abrindo NOVO CHAT na mesma conta...")
                self.abrir_novo_chat_limpo()
                continue

            except Exception as e:
                msg_limpa = str(e).splitlines()[0] if str(e).splitlines() else str(e)
                _log(f"⚠️ Erro durante validação ({msg_limpa}). Abrindo NOVO CHAT na mesma conta...")
                try:
                    self.abrir_novo_chat_limpo()
                except Exception:
                    pass
                
        # --- PROTEÇÃO ABSOLUTA DA TAREFA ---
        # Se o código chegou até aqui, significa que esgotou todas as tentativas na MESMA CONTA
        # e o Gemini só deu Timeout ou erro. 
        # Nós NÃO retornamos False. Levantamos um erro fatal para o main.py.
        raise Exception("Esgotaram as tentativas de validação por falhas na interface (Timeouts/Bugs). A conta será rotacionada para preservar a imagem.")

    def _selecionar_foto_produto(self, tarefa: Any) -> Optional[Path]:
        candidatos = self._listar_candidatos_produto(tarefa)
        if not candidatos:
            _log('Nenhuma imagem candidata encontrada na pasta da tarefa.')
            return None
        for candidato in candidatos:
            try:
                if self._validar_imagem_produto(candidato, timeout_resposta=40, max_reenvios_prompt=1):
                    _log(f'Foto do produto selecionada: {candidato.name}')
                    return candidato
            except Exception:
                pass
        _log('Nenhum candidato foi aprovado como foto principal do produto.')
        return None

    def executar_fluxo_imagem_base(
        self,
        tarefa: Any,
        foto_produto_escolhida: Optional[Path] = None,
        max_versoes: int = 3,
        numero_roteiro: int = 1,
    ) -> Optional[Path]:
        dir_anuncio = Path(getattr(tarefa, 'folder_path', '.'))
        caminho_final = dir_anuncio / f'IMG_BASE_VALIDADA_Roteiro{numero_roteiro}.png'

        if foto_produto_escolhida is None:
            foto_produto_escolhida = self._selecionar_foto_produto(tarefa)
            if not foto_produto_escolhida:
                return None
        else:
            foto_produto_escolhida = Path(foto_produto_escolhida)

        dados_anuncio = getattr(tarefa, 'dados_anuncio', {})
        nome_prod = dados_anuncio.get('nome_produto', 'o produto')
        beneficios = dados_anuncio.get('beneficios_extras', '')
        contexto_produto = f"O produto é '{nome_prod}'. " + (f"Detalhes: {beneficios}." if beneficios else "")

        descricoes = getattr(tarefa, 'descricoes_prompts', {})
        desc_maos = descricoes.get('modelo', {}).get('maos', 'mãos femininas delicadas')
        desc_estilo = descricoes.get('modelo', {}).get('estilo', 'estética casual e elegante')

        # Usa atributos da tarefa e variáveis do .env — sem calcular de índices do path
        estilo_filmagem_pasta = getattr(tarefa, 'shoot_type', dir_anuncio.parts[-2])
        nome_modelo_pasta = getattr(tarefa, 'model_name', dir_anuncio.parts[-3])
        
        modelos_dir = Path(os.getenv('MODELOS_DIR', 'G:/Meu Drive/Config/Modelos'))
        caminho_foto_modelo = modelos_dir / f"{nome_modelo_pasta}.png"
        if not caminho_foto_modelo.exists():
            caminho_foto_modelo = modelos_dir / f"{nome_modelo_pasta}.jpg"

        imagens_geradas = []

        for v_idx in range(1, max_versoes + 1):
            _log(f'Gerando Imagem Base {v_idx}/{max_versoes} (Estilo: {estilo_filmagem_pasta})...')
            caminho_parcial = dir_anuncio / f'ImgCand_R{numero_roteiro}_v{v_idx}.png'
            
            self.abrir_novo_chat_limpo()
            
            # === GERAÇÃO DINÂMICA (lookup por tipo de filmagem) ===
            self.anexar_arquivo_local(foto_produto_escolhida)
            _log(f'[DEBUG] estilo_filmagem_pasta={estilo_filmagem_pasta} | precisa_modelo={precisa_de_modelo(estilo_filmagem_pasta)} | cam_modelo={caminho_foto_modelo} | existe={caminho_foto_modelo.exists()}')
            
            if precisa_de_modelo(estilo_filmagem_pasta):
                time.sleep(1.5)
                if caminho_foto_modelo.exists():
                    _log(f'[DEBUG] Anexando foto da modelo: {caminho_foto_modelo.name}')
                    self.anexar_arquivo_local(caminho_foto_modelo)
                else:
                    _log(f'[ERRO] Foto da modelo NAO encontrada: {caminho_foto_modelo}')
                    raise FileNotFoundError(f"Foto da modelo não encontrada em: {caminho_foto_modelo}")
            
            prompt_geracao = carregar_prompt_imagem(
                estilo_filmagem_pasta,
                desc_maos=desc_maos,
                desc_corpo=descricoes.get('modelo', {}).get('corpo', 'mulher jovem'),
                desc_estilo=desc_estilo,
                nome_modelo=descricoes.get('modelo', {}).get('nome', 'A Modelo'),
            )
            # Variação de cenário entre roteiros para evitar imagens idênticas
            _variacoes = [
                "\nScene setting: modern urban sidewalk, warm late-afternoon golden light.",
                "\nScene setting: clean studio with gradient background, cool lateral lighting.",
                "\nScene setting: premium lifestyle room with soft window light.",
            ]
            prompt_geracao += _variacoes[(numero_roteiro - 1 + v_idx - 1) % len(_variacoes)]

            total_antes = self.contar_imagens_geradas()
            if self.enviar_prompt(prompt_geracao, aguardar_resposta=False) == 'ERRO_F5':
                continue

            if not self.aguardar_nova_imagem(total_antes, timeout=120):
                continue

            baixou = False
            for _ in range(3):
                scroll_ao_fim(self.driver)
                if self.baixar_ultima_imagem(caminho_parcial):
                    baixou = True
                    break
                
            if baixou and caminho_parcial.exists():
                imagens_geradas.append(caminho_parcial)

        if not imagens_geradas:
            return None

        if len(imagens_geradas) == 1:
            shutil.copy2(str(imagens_geradas[0]), str(caminho_final))
            return caminho_final

        _log(f'Iniciando Direção de Arte (Júri IA) entre as {len(imagens_geradas)} versões geradas...')
        self.abrir_novo_chat_limpo()
        self.anexar_arquivo_local(foto_produto_escolhida)
        
        nomes_candidatos = []
        for img in imagens_geradas:
            time.sleep(1.5)
            self.anexar_arquivo_local(img)
            nomes_candidatos.append(img.name)

        # === CRITÉRIOS DO JÚRI (lookup dinâmico) ===
        criterios_juri = carregar_criterios_juri(estilo_filmagem_pasta)

        prompt_juri = PROMPT_JURI_CANDIDATOS_IMAGEM_BASE.format(
            nomes_candidatos=', '.join(nomes_candidatos),
            contexto_produto=contexto_produto,
            criterios_avaliacao=criterios_juri
        )
        
        resposta = self.enviar_prompt(prompt_juri, timeout=90, aguardar_resposta=True)
        
        if resposta in ('RECOVERY_TRIGGERED', 'TIMEOUT_ANALISE', 'SEM_RESPOSTA_UTIL', 'ERRO_F5', 'TIMEOUT', 'SILENT_RESET'):
            _log(f"⚠️ O Júri falhou por engasgo da interface. Assumindo a primeira imagem gerada como fallback.")
            vencedor_path = imagens_geradas[0]
        else:
            _log(f"Resposta do Júri:\n{resposta.strip()}")
            vencedor_path = None
            resposta_limpa = str(resposta).lower().strip()
            
            # LÓGICA DE REPROVAÇÃO TOTAL (VETO)
            if "nenhuma" in resposta_limpa.split("vencedor:")[-1] or "nenhuma" in resposta_limpa:
                _log("🚨 VETO DO JÚRI: O Gemini detectou aberrações em TODAS as candidatas!")
                _log("Deletando aberrações e forçando falha para recomeçar o ciclo...")
                for img_suja in imagens_geradas:
                    img_suja.unlink(missing_ok=True)
                raise Exception("Todas as imagens geradas foram reprovadas pelo Júri de Qualidade.")

            for candidato in imagens_geradas:
                if candidato.name.lower() in resposta_limpa:
                    vencedor_path = candidato
                    break
                    
            if not vencedor_path:
                _log(f"Aviso: O Júri não nomeou o vencedor corretamente. Assumindo Variante 1.")
                vencedor_path = imagens_geradas[0]

        _log(f'🏆 O JÚRI DA IA DECIDIU! A Imagem Vencedora é: {vencedor_path.name}')
        shutil.copy2(str(vencedor_path), str(caminho_final))
        # 🧹 Limpeza: remove candidatos intermediários (ImgCand_R*_v*.png)
        for img_temp in imagens_geradas:
            try:
                img_temp.unlink(missing_ok=True)
            except Exception:
                pass
        return caminho_final
    
    def treinar_e_gerar_roteiro(
        self,
        arquivos: List[Path],
        dados_produto: Dict,
        arquivo_ref: Optional[Path] = None,
        qtd_cenas: int = 3,
        qtd_variantes: int = 2,
        roteiros_anteriores: Optional[List[str]] = None,
        tarefa_obj: Optional[Any] = None,
        reusar_chat: bool = False
    ) -> str:
        id_pasta = dados_produto.get('nome', '1')
        scroll_ao_fim(self.driver)
        _log(f"Iniciando fase de roteirização (Tarefa {id_pasta})")
        salvar_print_debug(self.driver,"IA_ROTEIRO_INICIO")

        descricoes = getattr(tarefa_obj, 'descricoes_prompts', {}) if tarefa_obj else {}
        perfil_modelo = descricoes.get('modelo', {})
        estilo_filmagem = descricoes.get('filmagem', {})

        desc_maos = perfil_modelo.get('maos', 'mãos femininas')
        desc_corpo = perfil_modelo.get('corpo', 'mulher jovem')
        desc_estilo = perfil_modelo.get('estilo', 'estética casual')
        desc_nome_modelo = perfil_modelo.get('nome', 'A Modelo')

        nome_tipo_video = estilo_filmagem.get('nome', 'Vídeo Padrão')
        regras_video = estilo_filmagem.get('regras', '')

        prompt_mestre = carregar_prompt_roteiro_mestre(
            qtd_cenas=qtd_cenas,
            qtd_cenas_menos_1=qtd_cenas - 1,
            nome_modelo=desc_nome_modelo,
            desc_maos=desc_maos,
            desc_corpo=desc_corpo,
            desc_estilo=desc_estilo,
            nome_tipo_video=nome_tipo_video,
            regras_video=regras_video
        )
        prompt_mestre_linear = " ".join(prompt_mestre.split())

        texto_referencia_dinamico = "Nenhuma referência extra."
        if arquivo_ref:
            extensao = str(arquivo_ref).lower()
            if extensao.endswith(('.mp4', '.mov', '.webm', '.avi')):
                texto_referencia_dinamico = "O vídeo com fala validada."
            else:
                texto_referencia_dinamico = "Outra imagem detalhada para compor a explicação."

        instrucoes_teste_ab = ""
        if roteiros_anteriores:
            _log(f"Injetando {len(roteiros_anteriores)} roteiro(s) anterior(es) para forçar variação no Teste A/B...")
            textos_anteriores = "\n\n".join([f"--- ROTEIRO ANTERIOR ---\n{r}\n------------------------" for r in roteiros_anteriores])
            instrucoes_teste_ab = (
                "\n\nATENÇÃO MÁXIMA (TESTE A/B): Eu já criei os roteiros abaixo para este produto. "
                "Crie um roteiro 100% INÉDITO e DIFERENTE mudando a abordagem de venda.\n\n"
                f"{textos_anteriores}\n"
            )

        # Detecta imagens base nos arquivos anexados
        imgs_base = [a for a in arquivos if 'IA_' in str(a) or 'ImgCand' in str(a)]
        
        # Usa o shoot_type da tarefa para carregar regras específicas do tipo de filmagem
        tipo_filmagem_roteiro = getattr(tarefa_obj, 'shoot_type', '') if tarefa_obj else ''
        prompt_execucao = carregar_prompt_roteiro_execucao(
            tipo_filmagem_roteiro,
            qtd_cenas=qtd_cenas,
            qtd_cenas_menos_1=qtd_cenas - 1,
            qtd_variantes=qtd_variantes,
            texto_referencia_dinamico=texto_referencia_dinamico,
            nome_modelo=desc_nome_modelo,
            desc_maos=desc_maos,
            instrucoes_teste_ab=instrucoes_teste_ab
        )
        
        # 🎨 MAPEAMENTO DE IMAGENS: Quando 2 imagens base (A+B) são anexadas,
        # instrui o Gemini a usar cada imagem para sua respectiva variante
        if len(imgs_base) >= 2:
            _log(f"📸 Duas imagens base detectadas — Variante 1 → image_0, Variante 2 → image_1")
            prompt_execucao += (
                "\n\nIMPORTANT — IMAGE MAPPING FOR VARIANTS:\n"
                "I attached TWO different base images. Each variant MUST use its own image:\n"
                "- VARIANTE 1: use the FIRST attached image (image_0) as the base photo for all scenes\n"
                "- VARIANTE 2: use the SECOND attached image (image_1) as the base photo for all scenes\n"
                "Each scene prompt must reference the correct image for its variant. "
                "Write 'generated from image_0.png' for Variante 1 and 'generated from image_1.png' for Variante 2.\n"
            )
        
        prompt_execucao_linear = " ".join(prompt_execucao.split())

        # --- LOOP BLINDADO DE RETENTATIVA NA MESMA CONTA ---
        erros_conhecidos = ('RECOVERY_TRIGGERED', 'TIMEOUT', 'TIMEOUT_ANALISE', 'SEM_RESPOSTA_UTIL', 'ERRO_F5')
        
        # 🛡️ Padrões de RECUSA do Gemini — quando a IA se recusa a gerar o roteiro
        _padroes_recusa = [
            'não posso te ajudar',
            'nao posso te ajudar',
            'não posso ajudar',
            'nao posso ajudar',
            'não consigo ajudar',
            'nao consigo ajudar',
            "i can't help",
            "i cannot help",
            "i'm not able to",
            "i am not able to",
            'modelo de linguagem',
            'language model',
            'não é possível gerar',
            'nao e possivel gerar',
            'unable to generate',
            'não tenho capacidade',
            'nao tenho capacidade',
            'peço desculpas',
            'peco desculpas',
            "i'm sorry",
            "i apologize",
            'não é algo que eu',
            'nao e algo que eu',
            'contra as políticas',
            'against the policies',
            'contra minhas diretrizes',
        ]
        
        def _eh_recusa(texto: str) -> bool:
            """Detecta se a resposta do Gemini é uma recusa em vez de conteúdo real."""
            if not texto or len(texto) < 10:
                return False
            texto_lower = texto.lower()
            # Se é muito curto (< 200 chars) E contém padrão de recusa → recusa
            if len(texto) < 200 and any(p in texto_lower for p in _padroes_recusa):
                return True
            # Se NÃO tem nenhum indicador de roteiro real → recusa
            tem_cena = bool(re.search(r'\[cena\s*\d+\]', texto_lower))
            tem_variante = '=== variante' in texto_lower
            tem_voiceover = 'voiceover' in texto_lower
            tem_camera = 'camera' in texto_lower or 'câmera' in texto_lower
            if not any([tem_cena, tem_variante, tem_voiceover, tem_camera]):
                if any(p in texto_lower for p in _padroes_recusa):
                    return True
            return False
        
        for tentativa in range(1, 4):
            try:
                # ⚡ MODO RÁPIDO: Se reusar_chat=True, pula treino (chat já está treinado)
                if reusar_chat and tentativa == 1:
                    _log(f"⚡ REUSO DE CHAT: Pulando treinamento (chat já treinado). Anexando arquivos novos...")
                else:
                    # Fluxo completo: novo chat + treino
                    self.abrir_novo_chat_limpo()
                    
                    _log(f"Enviando Prompt Mestre de Treinamento (Tentativa {tentativa}/3)...")
                    res_treino = self.enviar_prompt(prompt_mestre_linear, timeout=120, aguardar_resposta=True)
                    
                    if res_treino in erros_conhecidos:
                         _log(f"⚠️ A interface engasgou no Treinamento ({res_treino}). Reiniciando chat...")
                         reusar_chat = False  # Próxima tentativa deve ser fluxo completo
                         continue

                    # 🛡️ GUARD: Verifica se o treino foi uma recusa
                    if _eh_recusa(res_treino):
                        _log(f"⚠️ Gemini RECUSOU o treinamento: \"{res_treino[:80]}...\". Reiniciando chat...")
                        salvar_print_debug(self.driver, "ROTEIRO_TREINO_RECUSA")
                        reusar_chat = False
                        continue

                # 📎 Anexa os arquivos (SEMPRE — R2 tem imagens diferentes de R1)
                for arq in arquivos:
                    caminho = Path(arq)
                    if caminho.exists():
                        self.anexar_arquivo_local(caminho)

                _log(f"Solicitando geração do roteiro em {qtd_cenas} cenas...")
                resposta = self.enviar_prompt(prompt_execucao_linear, timeout=120, aguardar_resposta=True)

                if resposta in erros_conhecidos:
                    _log(f"⚠️ A interface engasgou na Execução ({resposta}). Reiniciando chat...")
                    reusar_chat = False  # Próxima tentativa deve ser fluxo completo
                    continue

                # 🛡️ GUARD: Verifica se a resposta é uma recusa em vez de roteiro
                if _eh_recusa(resposta):
                    _log(f"⚠️ Gemini RECUSOU gerar o roteiro: \"{resposta[:80]}...\". Reiniciando chat...")
                    salvar_print_debug(self.driver, "ROTEIRO_EXECUCAO_RECUSA")
                    reusar_chat = False
                    continue

                # 🛡️ GUARD ANTI-VAZAMENTO: Detecta se a resposta é na verdade o texto do TREINO
                # Isso acontece quando o JS pega a model-response errada (índice antigo)
                _resp_lower = resposta.lower().strip() if resposta else ''
                _sinais_treino = ['sistema calibrado', 'system calibrated', 'understood', 'entendido', 'ok, entendi']
                if any(s in _resp_lower for s in _sinais_treino) and len(resposta) < 200:
                    _log(f"🚨 VAZAMENTO DE TREINO DETECTADO! Resposta é do treinamento, não do roteiro: \"{resposta[:60]}\". Retry...")
                    salvar_print_debug(self.driver, "ROTEIRO_VAZAMENTO_TREINO")
                    reusar_chat = False
                    continue
                
                # 🛡️ GUARD DE TAMANHO MÍNIMO: Um roteiro real com 3 cenas tem > 300 chars
                if len(resposta) < 300:
                    _log(f"⚠️ Resposta muito curta para ser roteiro ({len(resposta)} chars): \"{resposta[:80]}...\". Retry...")
                    salvar_print_debug(self.driver, "ROTEIRO_MUITO_CURTO")
                    reusar_chat = False
                    continue

                # 🎯 Marca que o chat está treinado e pronto para reuso
                self._chat_treinado = True
                
                salvar_print_debug(self.driver,"IA_ROTEIRO_GERADO")
                return resposta

            except Exception as e:
                msg_erro = str(e).splitlines()[0] if str(e).splitlines() else str(e)
                _log(f"⚠️ Erro na tentativa {tentativa} de gerar roteiro: {msg_erro}")
                
                # 🚨 Driver morto (Chrome crashou) — não adianta retry com o mesmo driver
                erro_lower = str(e).lower()
                if any(dead in erro_lower for dead in [
                    'max retries exceeded', 'connectionrefusederror', 
                    'newconnectionerror', 'winerror 10061',
                    'session not created', 'no such session'
                ]):
                    raise Exception(f"SWITCH_ACCOUNT: Chrome morreu durante geração de roteiro — {msg_erro[:80]}")

        # Se falhou 3 vezes na mesma conta, devolvemos erro fatal para o main rotacionar a conta
        raise Exception("Esgotaram as tentativas de gerar roteiro devido a falhas na interface do Gemini.")

    def avaliar_melhor_variante_de_video(self, videos_720p: List[Path], roteiro: str) -> Path:
        if not videos_720p:
            raise ValueError("Nenhum vídeo fornecido para avaliação.")
            
        if len(videos_720p) == 1:
            _log(f"Apenas uma variante detectada ({videos_720p[0].name}). Pulando júri.")
            return videos_720p[0]

        _log(f"Iniciando JÚRI DE DIREÇÃO DE ARTE para {len(videos_720p)} variantes (720p)...")
        salvar_print_debug(self.driver,"IA_JURI_VIDEO_INICIO")
        self.abrir_novo_chat_limpo()
        
        for video in videos_720p:
            if video.exists():
                self.anexar_arquivo_local(video)

        # ...
        prompt_juri = PROMPT_JURI_VIDEO.format(
            qtd_variantes=len(videos_720p),
            roteiro=roteiro
        )
        # ...

        _log("Solicitando a decisão ao Gemini...")
        resposta_ia = self.enviar_prompt(prompt_juri, timeout=60, aguardar_resposta=True)

        if not resposta_ia or "TIMEOUT" in resposta_ia or "ERRO" in resposta_ia:
            _log(f"Aviso: O Gemini falhou em avaliar ({resposta_ia}). Assumindo a Variante 1.")
            return videos_720p[0]

        resposta_limpa = resposta_ia.strip().replace("`", "").replace('"', "").replace("'", "")
        _log(f"Resposta do Diretor de Arte: {resposta_limpa}")
        salvar_print_debug(self.driver,"IA_JURI_VIDEO_DECISAO")

        for video in videos_720p:
            if video.name.lower() in resposta_limpa.lower():
                _log(f"🎉 Variante eleita: {video.name}")
                return video
                
        for video in videos_720p:
            if video.stem.lower() in resposta_limpa.lower():
                _log(f"🎉 Variante eleita (pelo radical): {video.name}")
                return video

        _log(f"Aviso: Não foi possível casar a resposta '{resposta_limpa}' com os arquivos. Assumindo Variante 1.")
        return videos_720p[0]
    
    def classificar_arquivos_e_extrair_dados(self, arquivos: list[Path]) -> dict | None:
        # Loop de 3 tentativas na mesma conta antes de desistir
        for tentativa_geral in range(1, 4):
            _log(f"Iniciando classificação de arquivos (Tentativa {tentativa_geral}/3 na mesma conta)...")
            self.abrir_novo_chat_limpo()
            
            nomes_arquivos = []
            
            # --- BLOCO TUDO OU NADA: ANEXO DE ARQUIVOS ---
            try:
                for arq in arquivos:
                    # Se der TimeoutException aqui, ele pula direto pro except abaixo
                    self.anexar_arquivo_local(arq)
                    nomes_arquivos.append(arq.name)
            except Exception as e:
                # 🚨 Identificou falha no anexo? Não tenta mais nada, vaza da conta!
                _log(f"🚨 FALHA CRÍTICA NO ANEXO: {str(e).splitlines()[0]}")
                _log("Interrompendo classificação. Solicitando troca de conta ao sistema principal...")
                # Levanta o erro para o main.py capturar e rodar o 'finally' (fechar driver)
                raise e

            # Se chegou aqui, todos os arquivos foram anexados. Agora sim manda o prompt.
            prompt = PROMPT_CLASSIFICACAO_ARQUIVOS.format(nomes_arquivos=', '.join(nomes_arquivos))
            # 🛡️ Timeout adaptativo: 120s se tem vídeo (MP4/MOV), 60s para só imagens
            tem_video = any(arq.suffix.lower() in ('.mp4', '.mov', '.avi', '.mkv', '.webm') for arq in arquivos)
            timeout_classif = 120 if tem_video else 60
            _log(f"Timeout de classificação: {timeout_classif}s {'(🎥 vídeo detectado)' if tem_video else ''}")
            resposta = self.enviar_prompt(prompt, timeout=timeout_classif, aguardar_resposta=True)

            # =================================================================
            # 🔄 RECOVERY para sinais de erro — refresh + limpar + novo chat
            # =================================================================
            if resposta in ('RECOVERY_TRIGGERED', 'ERRO_F5'):
                _log(f"🔄 Sinal '{resposta}' recebido. Recovery completo: refresh → espera → novo chat...")
                try:
                    self.driver.refresh()
                    time.sleep(3)
                    self._superar_bloqueios_e_onboarding()
                except Exception:
                    pass
                continue

            if resposta == 'SILENT_RESET':
                _log("🚨 Gemini resetou silenciosamente. Sinalizando restart do Chrome...")
                raise Exception("RESTART_CHROME: Gemini silent reset detectado")

            if not resposta or resposta in {'SEM_RESPOSTA_UTIL', 'TIMEOUT'}:
                _log("⚠️ Resposta inválida ou vazia. Tentando Recovery manual...")
                # Recovery: refresh antes da próxima tentativa
                try:
                    self.driver.refresh()
                    time.sleep(2)
                    self._superar_bloqueios_e_onboarding()
                except Exception:
                    pass
                continue

            # Processamento do JSON
            import json
            match = re.search(r'\{.*\}', resposta, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except Exception as e:
                    _log(f'Erro ao converter JSON: {e}')
            
            _log("⚠️ Falha ao extrair JSON da resposta. Tentando de novo...")
            
        # 🩺 HEALTH CHECK: Antes de desistir, verifica se a sessão Gemini está funcional
        _log("🩺 Executando Health Check antes de desistir...")
        try:
            self.abrir_novo_chat_limpo()
            resp_check = self.enviar_prompt("Responda apenas: OK", timeout=30, aguardar_resposta=True)
            if resp_check and 'OK' in str(resp_check).upper() and resp_check not in ('SEM_RESPOSTA_UTIL', 'TIMEOUT', 'SILENT_RESET', 'ERRO_F5'):
                _log("✅ Health Check passou! Gemini está funcional. Retentando classificação com Chrome limpo...")
                raise Exception("RESTART_CHROME: Health check OK mas classificação falhou - reiniciando Chrome")
            else:
                _log("❌ Health Check falhou. Sessão Gemini comprometida.")
        except Exception as e:
            if 'RESTART_CHROME' in str(e):
                raise
            _log(f"❌ Health Check erro: {str(e)[:80]}")
        
        _log("❌ Esgotadas as tentativas de classificação nesta conta.")
        return None