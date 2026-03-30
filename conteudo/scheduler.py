"""
Scheduler de geração contínua de vídeos.
Controla horários, personagens, temas e ciclos diários.
"""

import time
import random
from datetime import datetime, timedelta
from pathlib import Path

# Horários alvo de publicação (horas inteiras)
HORARIOS_PUBLICACAO = [9, 12, 17, 19, 21]

# Janelas de geração: começa X horas antes de cada horário alvo
ANTECEDENCIA_HORAS = 1.5

# Tolerância em minutos para considerar que está "na janela"
TOLERANCIA_MINUTOS = 30


def calcular_proxima_janela() -> datetime:
    """Retorna o início da próxima janela de geração."""
    agora = datetime.now()
    for hora in sorted(HORARIOS_PUBLICACAO):
        janela = agora.replace(hour=hora, minute=0, second=0, microsecond=0)
        janela -= timedelta(hours=ANTECEDENCIA_HORAS)
        if janela > agora:
            return janela
    # Se passou de todos os horários hoje, próxima janela é amanhã às 9h
    amanha = agora + timedelta(days=1)
    primeira = sorted(HORARIOS_PUBLICACAO)[0]
    janela = amanha.replace(hour=primeira, minute=0, second=0, microsecond=0)
    return janela - timedelta(hours=ANTECEDENCIA_HORAS)


def esta_em_janela_de_geracao() -> bool:
    """Verifica se o momento atual está dentro de uma janela de geração."""
    agora = datetime.now()
    for hora in HORARIOS_PUBLICACAO:
        alvo = agora.replace(hour=hora, minute=0, second=0, microsecond=0)
        inicio_janela = alvo - timedelta(hours=ANTECEDENCIA_HORAS)
        fim_janela    = alvo + timedelta(minutes=TOLERANCIA_MINUTOS)
        if inicio_janela <= agora <= fim_janela:
            return True
    return False


def aguardar_proxima_janela():
    """Bloqueia até o início da próxima janela de geração."""
    proxima = calcular_proxima_janela()
    agora   = datetime.now()
    espera  = (proxima - agora).total_seconds()

    if espera <= 0:
        return

    horas   = int(espera // 3600)
    minutos = int((espera % 3600) // 60)
    print(f"\n  ⏰ Próxima janela de geração: {proxima.strftime('%d/%m %H:%M')}")
    print(f"  ⏳ Aguardando {horas}h {minutos}min...")

    # Dorme em blocos de 60s para poder mostrar countdown
    while True:
        agora  = datetime.now()
        restam = (proxima - agora).total_seconds()
        if restam <= 0:
            break
        if restam > 300:
            time.sleep(60)
        else:
            time.sleep(10)