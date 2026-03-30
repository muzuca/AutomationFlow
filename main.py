"""
Ponto de entrada da automação de vídeos.
Suporta modo único e modo contínuo com janelas de horário.
"""

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
from conteudo.video_manager     import processar_videos
from automation_flow.flow_orchestrator import main as rodar_automacao

MAX_RETRIES_ROTEIRO = 3


def _linha(char: str = "═", largura: int = 55):
    print(char * largura)


def _gerar_roteiro_sem_repeticao(
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

        # Regra de uso do signo:
        # - Só usa signo se o tema_final for "signos"
        # - Caso contrário, passa um valor neutro
        if signo_e_relevante(tema_final):
            # Se o usuário configurou signo (fixo ou aleatorio), usa; senão, sorteia
            signo_base = signo_config or "aleatorio"
            signo_final = resolver_signo(signo_base)
        else:
            signo_final = "Todos os signos"  # neutro, não foca em um signo específico

        if tentativa > 1:
            variacoes = [
                "com foco em relacionamentos",
                "com foco em finanças",
                "com foco em saúde e bem-estar",
                "com foco em crescimento pessoal",
                "com foco em novos começos",
            ]
            mensagem += f" — {random.choice(variacoes)}"

        try:
            roteiro = gerar_roteiro(
                signo=signo_final,
                tema=tema_final,
                mensagem_central=mensagem,
                n_cenas=cenas_por_video,
            )
        except Exception as e:
            print(f"  ❌ Erro ao gerar roteiro (tentativa {tentativa}): {e}")
            continue

        if roteiro_e_repetido(personagem, tema_final, roteiro):
            if tentativa < MAX_RETRIES_ROTEIRO:
                print(f"  → Tentativa {tentativa + 1}/{MAX_RETRIES_ROTEIRO}...")
                time.sleep(2)
                continue
            else:
                print("  ⚠ Máximo de retries atingido. Usando roteiro atual mesmo assim.")

        return roteiro, tema_final, mensagem, signo_final

    return None, None, None, None


def executar_ciclo(config: dict):
    """
    Executa um ciclo completo de geração.
    Cada iteração de personagem = N vídeos distribuídos em janelas.
    """
    _linha()
    print(f"  INÍCIO DO CICLO — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    _linha()

    resultados = []
    qtd_videos_por_personagem = config["videos_por_personagem"]

    for personagem_cfg in config["personagens"]:
        pid    = personagem_cfg["id"]
        nome   = personagem_cfg["nome"]
        signo  = personagem_cfg["signo"]      # pode ser None
        tema   = personagem_cfg["tema"]
        cenas  = personagem_cfg["cenas_por_video"]

        signo_label = signo if signo else "—"

        print(f"\n{'─'*55}")
        print(f"  PERSONAGEM: {nome}")
        print(
            f"  Signo config: {signo_label} | Tema: {tema.capitalize()} "
            f"| Vídeos: {qtd_videos_por_personagem} | Cenas/vídeo: {cenas}"
        )
        print(f"{'─'*55}")

        videos_gerados = 0

        while videos_gerados < qtd_videos_por_personagem:
            print(f"\n  [VÍDEO {videos_gerados + 1}/{qtd_videos_por_personagem}]")

            roteiro, tema_final, mensagem, signo_final = _gerar_roteiro_sem_repeticao(
                personagem=pid,
                signo_config=signo,
                tema_escolhido=tema,
                cenas_por_video=cenas,
            )
            if roteiro is None:
                print("  ❌ Não foi possível gerar roteiro. Pulando este vídeo.")
                videos_gerados += 1
                continue

            print(
                f"  → Roteiro gerado com tema_final='{tema_final}' "
                f"e signo_final='{signo_final}'"
            )

            print(f"\n[AUTOMAÇÃO] Gerando {len(roteiro['prompts'])} cenas do roteiro...")
            arquivos = rodar_automacao(prompts=roteiro["prompts"])

            if not arquivos:
                print("  ❌ Nenhum vídeo gerado. Pulando.")
                videos_gerados += 1
                continue

            print("\n[VIDEO MANAGER] Processando vídeo final...")
            caminho_final = processar_videos(
                arquivos=arquivos,
                signo=signo_final,
                tema=tema_final,
            )

            if caminho_final:
                registrar_roteiro(
                    personagem=pid,
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
                print(f"  ✅ Vídeo {videos_gerados + 1} concluído: {caminho_final.name}")

            videos_gerados += 1

            if videos_gerados < qtd_videos_por_personagem:
                print(
                    f"\n  ⏸ {videos_gerados}/{qtd_videos_por_personagem} vídeos feitos. "
                    f"Aguardando próxima janela..."
                )
                aguardar_proxima_janela()

    _linha()
    print(f"\n  CICLO CONCLUÍDO — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Vídeos gerados com sucesso: {len(resultados)}")
    for r in resultados:
        print(f"    ✅ {r['personagem']} | {r['signo']} | {r['tema']} → {r['arquivo'].name}")
    _linha()

    return resultados


def main():
    print("\n")
    _linha("═")
    print("  AUTOMAÇÃO DE VÍDEOS — ANA CARTOMANTE")
    _linha("═")

    config = exibir_menu()

    modo = config["modo"]
    ciclo_num = 0

    if modo == "unico":
        ciclo_num += 1
        print(f"\n[CICLO #{ciclo_num}] Iniciando execução única...")
        executar_ciclo(config)
        print("\n✅ Execução única concluída.")
    else:
        print("\n[MODO CONTÍNUO] Sistema iniciado. Pressione Ctrl+C para encerrar.")
        print(f"  Horários de publicação: {[f'{h:02d}:00' for h in [9, 12, 17, 19, 21]]}")

        try:
            while True:
                ciclo_num += 1
                print(f"\n[CICLO #{ciclo_num}] {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
                executar_ciclo(config)
                print(f"\n  ✅ Ciclo #{ciclo_num} concluído.")
                aguardar_proxima_janela()
        except KeyboardInterrupt:
            print(f"\n\n  ⚠ Encerrado pelo usuário após {ciclo_num} ciclo(s).")
            print("  ✅ Até a próxima!\n")


if __name__ == "__main__":
    main()