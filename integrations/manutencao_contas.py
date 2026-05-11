# arquivo: integrations/manutencao_contas.py
# descricao: Daemon que roda em background validando contas Humble periodicamente.
# - Sincroniza contas do Humble
# - Tenta login em cada conta
# - Testa se Gemini responde
# - Cacheia perfil das contas saudáveis
# - Bane contas com 3 falhas consecutivas de manutenção

from __future__ import annotations

import os
import threading
import time
from datetime import datetime

from integrations.utils import _log
from integrations.conta_saude import (
    registrar_sucesso, registrar_falha, conta_esta_saudavel,
    sincronizar_saude, resumo_saude, LIMITE_FALHAS_AUTO_BAN
)


# Flag para parar o daemon graciosamente
_daemon_ativo = threading.Event()
_daemon_ativo.set()  # Começa ativo

# Lock para não conflitar com a execução principal
_lock_manutencao = threading.Lock()

# Flag para indicar que a manutenção está rodando
_em_manutencao = threading.Event()


def _validar_conta(settings, account) -> tuple[bool, str]:
    """Valida uma conta individual: login + teste Gemini.
    
    Returns:
        (sucesso: bool, motivo: str)
    """
    from integrations.browser import create_driver, close_driver
    from integrations.google_login import login_google
    
    driver = None
    try:
        # 1. Cria driver com perfil cacheado
        driver = create_driver(settings, email_perfil=account.email, thread_id=99)
        
        # 2. Tenta login (sem CAPTCHA — se aparecer, falha rápido)
        login_google(driver, settings, account, permitir_captcha=False)
        
        # 3. Testa se Gemini carrega
        _log(f"🧪 Testando Gemini para {account.email[:25]}...", "MANUTENCAO")
        driver.get(settings.gemini_url)
        time.sleep(5)
        
        url_final = driver.current_url
        if 'gemini.google.com' in url_final:
            # 4. Verifica se a interface de chat está acessível
            from selenium.webdriver.common.by import By
            chat_elements = driver.find_elements(By.CSS_SELECTOR, 
                'div[contenteditable="true"], textarea, rich-textarea')
            
            if chat_elements:
                _log(f"✅ {account.email[:25]}... — Gemini respondendo!", "MANUTENCAO")
                return True, "Gemini OK"
            else:
                _log(f"⚠️ {account.email[:25]}... — Gemini carregou mas sem chat", "MANUTENCAO")
                return False, "Gemini sem interface de chat"
        else:
            _log(f"❌ {account.email[:25]}... — Gemini não carregou: {url_final[:60]}", "MANUTENCAO")
            return False, f"Redirecionado para: {url_final[:60]}"
    
    except Exception as e:
        erro = str(e)[:100]
        _log(f"❌ {account.email[:25]}... — Falha: {erro}", "MANUTENCAO")
        
        # Classifica o tipo de falha
        if "CAPTCHA_IN_WORKER" in erro:
            return False, "CAPTCHA (perfil novo)"
        elif "SWITCH_ACCOUNT" in erro:
            return False, "Verificação de identidade"
        elif "CREDENTIALS_EXPIRED" in erro:
            return False, "Senha expirada"
        else:
            return False, erro
    
    finally:
        if driver:
            try:
                close_driver(driver)
            except:
                pass


def _executar_manutencao(settings_factory):
    """Executa um ciclo completo de manutenção de todas as contas.
    
    Args:
        settings_factory: Função que retorna settings atualizadas (get_settings)
    """
    _em_manutencao.set()
    
    try:
        _log("=" * 60, "MANUTENCAO")
        _log("🔧 INICIANDO CICLO DE MANUTENÇÃO DE CONTAS", "MANUTENCAO")
        _log("=" * 60, "MANUTENCAO")
        
        # 1. Sincroniza contas do Humble
        _log("📡 Sincronizando contas do Humble...", "MANUTENCAO")
        try:
            from integrations.acesso_humble import sincronizar_humble
            sincronizar_humble()
        except Exception as e:
            _log(f"⚠️ Falha ao sincronizar Humble: {e}", "MANUTENCAO")
        
        # 2. Recarrega settings com contas atualizadas
        settings = settings_factory()
        accounts = settings.accounts
        
        if not accounts:
            _log("⚠️ Nenhuma conta encontrada. Pulando manutenção.", "MANUTENCAO")
            return
        
        # 3. Sincroniza saúde com lista atual
        sincronizar_saude([acc.email for acc in accounts])
        
        _log(f"📋 {len(accounts)} contas para validar. {resumo_saude()}", "MANUTENCAO")
        
        # 4. Valida cada conta sequencialmente
        ok_count = 0
        fail_count = 0
        skip_count = 0
        
        for i, account in enumerate(accounts):
            if not _daemon_ativo.is_set():
                _log("⏹️ Manutenção interrompida por shutdown.", "MANUTENCAO")
                break
            
            _log(f"── [{i+1}/{len(accounts)}] Validando: {account.email[:30]}...", "MANUTENCAO")
            
            # Pula contas já banidas
            if not conta_esta_saudavel(account.email):
                _log(f"   🚫 Já banida. Pulando.", "MANUTENCAO")
                skip_count += 1
                continue
            
            sucesso, motivo = _validar_conta(settings, account)
            
            if sucesso:
                registrar_sucesso(account.email)
                ok_count += 1
            else:
                status = registrar_falha(account.email, motivo=motivo)
                fail_count += 1
                if status == "banida":
                    _log(f"   🚫 AUTO-BANIDA após falhas consecutivas!", "MANUTENCAO")
            
            # Pausa entre contas para não sobrecarregar
            if i < len(accounts) - 1:
                time.sleep(3)
        
        # 5. Resumo final
        _log("=" * 60, "MANUTENCAO")
        _log(f"🔧 MANUTENÇÃO CONCLUÍDA: ✅{ok_count} | ❌{fail_count} | ⏭️{skip_count}", "MANUTENCAO")
        _log(f"📊 {resumo_saude()}", "MANUTENCAO")
        _log("=" * 60, "MANUTENCAO")
        
        # 📋 Gera relatório visual em logs/status_contas.txt
        from integrations.conta_saude import gerar_relatorio_status
        relatorio = gerar_relatorio_status()
        _log(f"📋 Relatório salvo em logs/status_contas.txt", "MANUTENCAO")
    
    except Exception as e:
        _log(f"🚨 Erro crítico na manutenção: {e}", "MANUTENCAO")
    
    finally:
        _em_manutencao.clear()


def _loop_daemon(settings_factory, intervalo_horas: float):
    """Loop principal do daemon — roda indefinidamente."""
    _log(f"🔧 Daemon de manutenção iniciado (intervalo: {intervalo_horas}h)", "MANUTENCAO")
    
    # Primeira execução após 5 minutos (dá tempo do main arrancar)
    primeiro_delay = 5 * 60
    _log(f"⏰ Primeira manutenção em {primeiro_delay // 60} minutos...", "MANUTENCAO")
    
    # Espera o delay inicial (mas verifica shutdown a cada 10s)
    inicio = time.time()
    while time.time() - inicio < primeiro_delay:
        if not _daemon_ativo.is_set():
            return
        time.sleep(10)
    
    while _daemon_ativo.is_set():
        try:
            with _lock_manutencao:
                _executar_manutencao(settings_factory)
        except Exception as e:
            _log(f"🚨 Erro no daemon: {e}", "MANUTENCAO")
        
        # Aguarda o próximo ciclo (verifica shutdown a cada 30s)
        proximo = intervalo_horas * 3600
        _log(f"⏰ Próxima manutenção em {intervalo_horas}h", "MANUTENCAO")
        inicio_espera = time.time()
        while time.time() - inicio_espera < proximo:
            if not _daemon_ativo.is_set():
                return
            time.sleep(30)


def iniciar_daemon_manutencao(settings_factory) -> threading.Thread | None:
    """Inicia o daemon de manutenção em background.
    
    Args:
        settings_factory: Função que retorna settings atualizadas
    Returns:
        Thread do daemon ou None se desabilitado
    """
    intervalo = float(os.getenv("INTERVALO_MANUTENCAO_HORAS", "0"))
    
    if intervalo <= 0:
        _log("🔧 Daemon de manutenção DESABILITADO (INTERVALO_MANUTENCAO_HORAS=0)", "MANUTENCAO")
        return None
    
    _daemon_ativo.set()
    
    thread = threading.Thread(
        target=_loop_daemon,
        args=(settings_factory, intervalo),
        daemon=True,  # Morre quando o programa principal encerra
        name="DaemonManutencao"
    )
    thread.start()
    
    return thread


def parar_daemon_manutencao():
    """Para o daemon graciosamente."""
    _daemon_ativo.clear()
    _log("⏹️ Daemon de manutenção sinalizado para parar.", "MANUTENCAO")


def esta_em_manutencao() -> bool:
    """Retorna True se a manutenção está rodando agora."""
    return _em_manutencao.is_set()
