# arquivo: integrations/conta_saude.py
# descricao: Sistema de rastreamento de saúde das contas Humble.
# Cada conta tem um registro de falhas, sucessos e status.
# Contas com muitas falhas consecutivas são automaticamente
# marcadas como "banida" e puladas no rodízio.

from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from integrations.utils import _log

# Arquivo de persistência
ARQUIVO_SAUDE = Path("logs/contas_saude.json")
_lock = threading.Lock()

# Quantas falhas consecutivas para banir automaticamente (configurável via .env)
import os
LIMITE_FALHAS_AUTO_BAN = int(os.getenv("LIMITE_FALHAS_BAN", "5"))


def _carregar() -> dict:
    """Carrega o registro de saúde do disco."""
    if not ARQUIVO_SAUDE.exists():
        return {}
    try:
        with open(ARQUIVO_SAUDE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def _salvar(dados: dict) -> None:
    """Salva o registro de saúde no disco."""
    ARQUIVO_SAUDE.parent.mkdir(parents=True, exist_ok=True)
    with open(ARQUIVO_SAUDE, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2, ensure_ascii=False)


def _obter_registro(dados: dict, email: str) -> dict:
    """Retorna o registro de uma conta (cria se não existir)."""
    if email not in dados:
        dados[email] = {
            "status": "ok",             # ok | banida | cooldown
            "falhas_seguidas": 0,
            "total_sucessos": 0,
            "total_falhas": 0,
            "ultimo_sucesso": None,
            "ultima_falha": None,
            "motivo_bloqueio": None,
        }
    return dados[email]


def registrar_sucesso(email: str) -> None:
    """Marca uma conta como saudável após uso bem-sucedido."""
    with _lock:
        dados = _carregar()
        reg = _obter_registro(dados, email)
        reg["status"] = "ok"
        reg["falhas_seguidas"] = 0
        reg["total_sucessos"] += 1
        reg["ultimo_sucesso"] = datetime.now().isoformat()
        reg["motivo_bloqueio"] = None
        _salvar(dados)


def registrar_falha(email: str, motivo: str = "") -> str:
    """Registra uma falha e retorna o status atualizado da conta.
    
    Returns:
        'ok' se ainda pode tentar, 'banida' se atingiu o limite.
    """
    with _lock:
        dados = _carregar()
        reg = _obter_registro(dados, email)
        reg["falhas_seguidas"] += 1
        reg["total_falhas"] += 1
        reg["ultima_falha"] = datetime.now().isoformat()
        
        if reg["falhas_seguidas"] >= LIMITE_FALHAS_AUTO_BAN:
            reg["status"] = "banida"
            reg["motivo_bloqueio"] = motivo or f"Auto-ban: {LIMITE_FALHAS_AUTO_BAN} falhas consecutivas"
            _log(f"🚫 Conta AUTO-BANIDA: {email[:30]}... ({reg['motivo_bloqueio']})", "SAUDE")
        
        _salvar(dados)
        return reg["status"]


def banir_conta(email: str, motivo: str = "Banida manualmente") -> None:
    """Bane uma conta manualmente (ex: conta suspensa pelo Google)."""
    with _lock:
        dados = _carregar()
        reg = _obter_registro(dados, email)
        reg["status"] = "banida"
        reg["motivo_bloqueio"] = motivo
        _salvar(dados)
        _log(f"🚫 Conta BANIDA: {email[:30]}... — {motivo}", "SAUDE")


def desbanir_conta(email: str) -> None:
    """Remove o ban de uma conta (reset total)."""
    with _lock:
        dados = _carregar()
        reg = _obter_registro(dados, email)
        reg["status"] = "ok"
        reg["falhas_seguidas"] = 0
        reg["motivo_bloqueio"] = None
        _salvar(dados)
        _log(f"✅ Conta DESBANIDA: {email[:30]}...", "SAUDE")


def conta_esta_saudavel(email: str) -> bool:
    """Retorna True se a conta pode ser usada no rodízio."""
    with _lock:
        dados = _carregar()
        reg = _obter_registro(dados, email)
        return reg["status"] == "ok"


def obter_status(email: str) -> dict:
    """Retorna o registro completo de uma conta."""
    with _lock:
        dados = _carregar()
        return _obter_registro(dados, email)


def filtrar_contas_saudaveis(contas: list) -> list:
    """Filtra uma lista de contas, removendo as banidas.
    
    Args:
        contas: Lista de objetos com atributo .email
    Returns:
        Lista filtrada (só contas com status 'ok')
    """
    with _lock:
        dados = _carregar()
        saudaveis = []
        banidas = []
        
        for conta in contas:
            reg = _obter_registro(dados, conta.email)
            if reg["status"] == "ok":
                saudaveis.append(conta)
            else:
                banidas.append(f"{conta.email[:25]}... ({reg['motivo_bloqueio']})")
        
        if banidas:
            _log(f"🚫 {len(banidas)} conta(s) banida(s) removidas do rodízio: {', '.join(banidas)}", "SAUDE")
        
        _salvar(dados)  # Persiste registros criados para contas novas
        return saudaveis


def resumo_saude() -> str:
    """Retorna um resumo legível do estado de todas as contas."""
    dados = _carregar()
    if not dados:
        return "Nenhum registro de saúde ainda."
    
    ok = sum(1 for r in dados.values() if r.get("status") == "ok")
    ban = sum(1 for r in dados.values() if r.get("status") == "banida")
    
    return f"Contas: {ok} saudáveis | {ban} banidas | {len(dados)} total"


def sincronizar_saude(emails_ativos: list[str]) -> int:
    """Remove do contas_saude.json contas que não existem mais no .env.
    
    Args:
        emails_ativos: Lista de emails que existem atualmente no .env
    Returns:
        Número de entradas removidas
    """
    with _lock:
        dados = _carregar()
        if not dados:
            return 0
        
        emails_set = set(e.strip().lower() for e in emails_ativos)
        removidos = []
        
        for email in list(dados.keys()):
            if email.strip().lower() not in emails_set:
                removidos.append(email)
                del dados[email]
        
        if removidos:
            _salvar(dados)
            _log(f"🧹 {len(removidos)} conta(s) removida(s) do registro de saúde (não existem mais no .env)", "SAUDE")
        
        return len(removidos)


def gerar_relatorio_status() -> str:
    """Gera um relatório visual do status de todas as contas.
    
    Salva em logs/status_contas.txt e retorna o conteúdo.
    """
    with _lock:
        dados = _carregar()
    
    if not dados:
        return "(Nenhuma conta registrada)"
    
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    linhas = [
        f"{'='*70}",
        f"  STATUS DAS CONTAS HUMBLE — Atualizado: {agora}",
        f"{'='*70}",
        ""
    ]
    
    # Ordena: quentes primeiro, depois novas, depois banidas
    def sort_key(item):
        email, reg = item
        if reg["status"] == "banida": return (2, email)
        if reg.get("ultimo_sucesso"): return (0, email)
        return (1, email)
    
    for email, reg in sorted(dados.items(), key=sort_key):
        status = reg["status"]
        falhas = reg.get("falhas_seguidas", 0)
        sucessos = reg.get("total_sucessos", 0)
        ultimo_ok = reg.get("ultimo_sucesso", "nunca")
        motivo = reg.get("motivo_bloqueio", "")
        
        if status == "banida":
            icone = "❌ BANIDA "
            detalhe = f"| Motivo: {motivo}" if motivo else ""
        elif sucessos > 0 and falhas == 0:
            icone = "✅ QUENTE "
            detalhe = f"| Último OK: {ultimo_ok}"
        elif sucessos > 0:
            icone = "⚠️ INSTÁVEL"
            detalhe = f"| {falhas} falha(s) | Último OK: {ultimo_ok}"
        else:
            icone = "⏳ NOVA   "
            detalhe = "| Nunca validada"
        
        linhas.append(f"  {icone} | {email:<45} {detalhe}")
    
    linhas.append("")
    linhas.append(f"{'='*70}")
    
    # Contadores
    quentes = sum(1 for r in dados.values() if r["status"] == "ok" and r.get("total_sucessos", 0) > 0)
    banidas = sum(1 for r in dados.values() if r["status"] == "banida")
    novas = sum(1 for r in dados.values() if r.get("total_sucessos", 0) == 0 and r["status"] != "banida")
    
    linhas.append(f"  RESUMO: ✅ {quentes} quentes | ⏳ {novas} novas | ❌ {banidas} banidas")
    linhas.append(f"{'='*70}")
    
    conteudo = "\n".join(linhas)
    
    # Salva em arquivo
    caminho = Path("logs/status_contas.txt")
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        f.write(conteudo)
    
    return conteudo
