# main.py — Ponto de entrada da automação de vídeos.
# Suporta modo único e modo contínuo com janelas de horário.

import sys
import time
import random
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conteudo.menu              import exibir_menu
from conteudo.temas             import resolver_tema
from conteudo.historico         import registrar_roteiro, roteiro_e_repetido
from conteudo.scheduler         import aguardar_proxima_janela
from conteudo.roteiro_generator import gerar_roteiro
from conteudo.video_manager      import processar_videos

MAX_RETRIES_ROTEIRO = 3


def linha(char: str = "=", largura: int = 55):
    print(char * largura)


def _resolver_motor(motor: str):
    """
    Retorna a função main() do orquestrador correto.
    O import é feito aqui (lazy) para não exigir dependências
    do Guru instaladas quando só o Humble for usado, e vice-versa.
    """
    if motor == "humble":
        from automation_flow.humble_orchestrator import main as fn
        return fn
    else:  # "guru" — padrão
        from automation_flow.flow_orchestrator import main as fn
        return fn


def gerar_roteiro_sem_repeticao(
    personagem: str,
    signo_config: str | None,
    tema_escolhido: str,
    cenas_por_video: int,
) -> tuple[dict, str, str, str] | tuple[None, None, None, None]:
    """
    Gera roteiro verificando histórico para evitar repetições.
    Retorna (roteiro, tema_final, mensagem_central, signo_final)
    ou (None, None, None, None) em caso de falha.
    """
    from conteudo.temas import resolver_signo, signo_e_relevante

    for tentativa in range(1, MAX_RETRIES_ROTEIRO + 1):
        tema_final, mensagem = resolver_tema(personagem, tema_escolhido)

        if signo_e_relevante(tema_final):
            signo_base  = signo_config or "aleatorio"
            signo_final = resolver_signo(signo_base)
        else:
            signo_final = "Todos os signos"

        if tentativa > 1:
            variacoes = [
                "com foco em relacionamentos",
                "com foco em finanças",
                "com foco em saúde e bem-estar",
                "com foco em crescimento pessoal",
                "com foco em novos começos",
            ]
            mensagem = f"{mensagem} {random.choice(variacoes)}"

        try:
            roteiro = gerar_roteiro(
                signo=signo_final,
                tema=tema_final,
                mensagem_central=mensagem,
                n_cenas=cenas_por_video,
            )
        except Exception as e:
            print(f"⚠ Erro ao gerar roteiro (tentativa {tentativa}): {e}")
            continue

        if roteiro_e_repetido(personagem, tema_final, roteiro):
            if tentativa < MAX_RETRIES_ROTEIRO:
                print(f"⚠ Roteiro repetido. Tentativa {tentativa + 1}/{MAX_RETRIES_ROTEIRO}...")
                time.sleep(2)
                continue
            else:
                print("⚠ Máximo de retries atingido. Usando roteiro atual mesmo assim.")

        return roteiro, tema_final, mensagem, signo_final

    return None, None, None, None


def executar_ciclo(config: dict):
    """Executa um ciclo completo de geração para todos os personagens."""
    linha()
    print(f"  INÍCIO DO CICLO — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    linha()

    # Resolve o motor UMA vez por ciclo
    motor           = config.get("motor", "guru")
    rodar_automacao = _resolver_motor(motor)
    label_motor     = "Guru" if motor == "guru" else "Humble"

    resultados                = []
    qtd_videos_por_personagem = config["videos_por_personagem"]

    for personagem_cfg in config["personagens"]:
        pid   = personagem_cfg["id"]
        nome  = personagem_cfg["nome"]
        signo = personagem_cfg["signo"]
        tema  = personagem_cfg["tema"]
        cenas = personagem_cfg["cenas_por_video"]

        signo_label = signo if signo else "—"

        linha("-", 55)
        print(f"  PERSONAGEM: {nome}")
        print(f"  Signo config: {signo_label} | Tema: {tema.capitalize()}")
        print(f"  Motor: {label_motor} | Vídeos: {qtd_videos_por_personagem} | Cenas/vídeo: {cenas}")
        linha("-", 55)

        videos_gerados = 0
        while videos_gerados < qtd_videos_por_personagem:
            print(f"\n  VÍDEO {videos_gerados + 1}/{qtd_videos_por_personagem}")

            roteiro, tema_final, mensagem, signo_final = gerar_roteiro_sem_repeticao(
                personagem=pid,
                signo_config=signo,
                tema_escolhido=tema,
                cenas_por_video=cenas,
            )

            if roteiro is None:
                print("⚠ Não foi possível gerar roteiro. Pulando este vídeo.")
                videos_gerados += 1
                continue

            print(f"✔ Roteiro gerado — tema: {tema_final} | signo: {signo_final}")
            print(f"  [{label_motor}] Gerando {len(roteiro['prompts'])} cenas...")

            arquivos = rodar_automacao(prompts=roteiro["prompts"])

            if not arquivos:
                print("⚠ Nenhum vídeo gerado. Pulando.")
                videos_gerados += 1
                continue

            print("  VIDEO MANAGER: Processando vídeo final...")
            caminho_final = processar_videos(
                arquivos=arquivos,
                signo=signo_final,
                tema=tema_final,
            )

            if caminho_final:
                registrar_roteiro(
                    pid,
                    signo=signo_final,
                    tema=tema_final,
                    roteiro=roteiro,
                )
                resultados.append({
                    "personagem": nome,
                    "arquivo":    caminho_final,
                    "tema":       tema_final,
                    "signo":      signo_final,
                })
                print(f"✔ Vídeo {videos_gerados + 1} concluído: {caminho_final.name}")

            videos_gerados += 1

            if videos_gerados < qtd_videos_por_personagem:
                print(f"  {videos_gerados}/{qtd_videos_por_personagem} vídeos feitos. Aguardando próxima janela...")
                aguardar_proxima_janela()

    linha()
    print(f"  CICLO CONCLUÍDO — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Vídeos gerados com sucesso: {len(resultados)}")
    for r in resultados:
        print(f"  {r['personagem']} | {r['signo']} | {r['tema']} | {r['arquivo'].name}")
    linha()

    return resultados


def main():
    linha()
    print("  AUTOMAÇÃO DE VÍDEOS — ANA CARTOMANTE")
    linha()

    config    = exibir_menu()
    modo      = config["modo"]
    ciclo_num = 0

    if modo == "unico":
        ciclo_num = 1
        print(f"\nCICLO {ciclo_num} — Iniciando execução única...")
        executar_ciclo(config)
        print("Execução única concluída.")
    else:
        print("\nMODO CONTÍNUO — Sistema iniciado. Pressione Ctrl+C para encerrar.")
        print(f"Horários de publicação: {' | '.join(f'{h:02d}:00' for h in [9, 12, 17, 19, 21])}")
        try:
            while True:
                ciclo_num += 1
                print(f"\nCICLO {ciclo_num} — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
                executar_ciclo(config)
                print(f"  Ciclo {ciclo_num} concluído.")
                aguardar_proxima_janela()
        except KeyboardInterrupt:
            print(f"\nEncerrado pelo usuário após {ciclo_num} ciclos. Até a próxima!")


if __name__ == "__main__":
    main()