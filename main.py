# main.py
import sys
import time
import random
from pathlib import Path
from datetime import datetime


from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env", override=True)


sys.path.insert(0, str(PROJECT_ROOT))


from automation_flow.flows.content import personas
from automation_flow.flows.content.menu import exibir_menu
from automation_flow.flows.content.historico import registrar_roteiro, roteiro_e_repetido
from automation_flow.flows.content.scheduler import aguardar_proxima_janela
from automation_flow.flows.content.video_manager import processar_videos
from acesso_humble import sincronizar_credenciais_humble



MAX_RETRIES_ROTEIRO = 3
VARIACOES_MENSAGEM = [
    "com foco em relacionamentos",
    "com foco em finanças",
    "com foco em saúde e bem-estar",
    "com foco em crescimento pessoal",
    "com foco em novos começos",
]



def linha(char: str = "=", largura: int = 55) -> None:
    print(char * largura)



def _resolver_motor(motor: str):
    if motor == "humble":
        from automation_flow.core.flow.humble_orchestrator import main as fn
        return fn, "Humble"
    from automation_flow.core.flow.guru_orchestrator import main as fn
    return fn, "Guru"



def _resolver_signo(persona, signo_config: str | None, tema_final: str) -> str | None:
    if not persona.USA_SIGNOS:
        return None

    if persona.tema_exige_signo(tema_final):
        base = signo_config or "aleatorio"
        if base == "aleatorio":
            signo = random.choice(persona.SIGNOS)
            print(f"  🎲 Signo aleatório sorteado: {signo}")
            return signo
        return base

    return "Todos os signos"



def _resolver_tema(persona, tema_escolhido: str) -> tuple[str, str]:
    temas_fixos = [t for t in persona.TEMAS if t != "aleatorio"]

    if tema_escolhido == "aleatorio":
        tema_final = random.choice(temas_fixos)
        print(f"  🎲 Tema aleatório sorteado: {tema_final}")
    else:
        tema_final = tema_escolhido

    mensagem = persona.TEMAS.get(tema_final)
    if mensagem is None:
        mensagem = persona.fallback_mensagem(tema_final)

    return tema_final, mensagem



def gerar_roteiro_sem_repeticao(
    pid: str,
    signo_config: str | None,
    tema_escolhido: str,
    cenas_por_video: int,
) -> tuple[dict, str, str, str | None] | tuple[None, None, None, None]:
    persona = personas.obter(pid)

    for tentativa in range(1, MAX_RETRIES_ROTEIRO + 1):
        tema_final, mensagem = _resolver_tema(persona, tema_escolhido)
        signo_final = _resolver_signo(persona, signo_config, tema_final)

        if tentativa > 1:
            mensagem = f"{mensagem} {random.choice(VARIACOES_MENSAGEM)}"

        try:
            roteiro = persona.gerar_roteiro(
                tema=tema_final,
                mensagem_central=mensagem,
                signo=signo_final,
                n_cenas=cenas_por_video,
            )
        except Exception as e:
            print(f"⚠ Erro ao gerar roteiro (tentativa {tentativa}): {e}")
            continue

        if roteiro_e_repetido(pid, tema_final, roteiro):
            if tentativa < MAX_RETRIES_ROTEIRO:
                print(
                    f"⚠ Roteiro repetido. Tentativa {tentativa + 1}/"
                    f"{MAX_RETRIES_ROTEIRO}..."
                )
                time.sleep(2)
                continue
            print("⚠ Máximo de retries atingido. Usando roteiro atual mesmo assim.")

        return roteiro, tema_final, mensagem, signo_final

    return None, None, None, None



def executar_ciclo(config: dict):
    linha()
    print(f"  INÍCIO DO CICLO — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    linha()

    # >>> Sincroniza os acessos do Humble a cada ciclo
    sincronizar_credenciais_humble()

    motor = config.get("motor", "guru")
    rodar_automacao, label_motor = _resolver_motor(motor)
    resultados: list[dict] = []
    qtd = config["videos_por_personagem"]

    for rodada in range(1, qtd + 1):
        print(f"\n========== RODADA {rodada}/{qtd} ==========")

        for pcfg in config["personagens"]:
            pid = pcfg["id"]
            nome = pcfg["nome"]
            signo = pcfg.get("signo")
            tema = pcfg["tema"]
            cenas = pcfg["cenas_por_video"]

            linha("-", 55)
            print(f"  PERSONAGEM: {nome}")
            print(f"  Signo config: {signo or '—'} | Tema: {tema.capitalize()}")
            print(
                f"  Motor: {label_motor} | Vídeo desta rodada: "
                f"{rodada}/{qtd} | Cenas/vídeo: {cenas}"
            )
            linha("-", 55)
            print(f"\n  VÍDEO {rodada}/{qtd} — {nome}")

            roteiro, tema_final, mensagem, signo_final = gerar_roteiro_sem_repeticao(
                pid=pid,
                signo_config=signo,
                tema_escolhido=tema,
                cenas_por_video=cenas,
            )

            if roteiro is None:
                print("⚠ Não foi possível gerar roteiro. Pulando.")
                continue

            print(
                f"✔ Roteiro gerado — tema: {tema_final} | "
                f"signo: {signo_final or '—'}"
            )
            print(f"  [{label_motor}] Gerando {len(roteiro['prompts'])} cenas...")

            arquivos = None
            try:
                arquivos = rodar_automacao(prompts=roteiro["prompts"])
            except Exception as e:
                print(f"⚠ Erro ao gerar vídeo com motor {label_motor}: {e}")
                print("⚠ Pulando este vídeo e seguindo para o próximo personagem.")
                continue

            if not arquivos:
                print("⚠ Nenhum vídeo gerado. Pulando.")
                continue

            print("  VIDEO MANAGER: Processando vídeo final...")
            caminho_final = processar_videos(
                personagem=pid,
                arquivos=arquivos,
                tema=tema_final,
                signo=signo_final,
            )

            if caminho_final:
                registrar_roteiro(
                    pid,
                    signo=signo_final or "—",
                    tema=tema_final,
                    roteiro=roteiro,
                )
                resultados.append(
                    {
                        "personagem": nome,
                        "arquivo": caminho_final,
                        "tema": tema_final,
                        "signo": signo_final or "—",
                    }
                )
                print(
                    f"✔ Vídeo {rodada} de {nome} concluído: "
                    f"{caminho_final.name}"
                )

        if rodada < qtd:
            print(f"\n>>> Rodada {rodada} concluída para todos os personagens.")
            print("    Aguardando próxima janela de publicação...")
            aguardar_proxima_janela()

    linha()
    print(f"  CICLO CONCLUÍDO — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    print(f"  Vídeos gerados com sucesso: {len(resultados)}")
    for r in resultados:
        print(
            f"  {r['personagem']} | {r['signo']} | "
            f"{r['tema']} | {r['arquivo'].name}"
        )
    linha()
    return resultados


# ===========================================================================
# ANÚNCIOS DE PRODUTOS — novo fluxo
# ===========================================================================

def executar_anuncios(config: dict):
    from automation_flow.flows.anuncios.watcher import (
        coletar_tarefas,
        monitorar_loop,
        garantir_estrutura,
    )

    modelos = config.get("modelos")
    tipos   = config.get("tipos_filmagem")
    modo    = config.get("modo", "continuo")

    garantir_estrutura()

    def processar_tarefas(tarefas):
        linha()
        print(
            f"  ANÚNCIOS — {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} — "
            f"{len(tarefas)} tarefa(s) detectada(s)"
        )
        linha()
        for tarefa in tarefas:
            print(f"\n  → {tarefa}")
            print("  [FASE 2] Gemini browser — geração de imagem: em breve.")
            print("  [FASE 3] Flow/Veo3     — geração de vídeo:   em breve.")

    if modo == "unico":
        tarefas = coletar_tarefas(
            modelos_filtro=modelos,
            tipos_filtro=tipos,
        )
        if tarefas:
            processar_tarefas(tarefas)
        else:
            print("  Nenhuma imagem pendente encontrada. Encerrando.")
    else:
        monitorar_loop(
            callback=processar_tarefas,
            modelos_filtro=modelos,
            tipos_filtro=tipos,
            intervalo_segundos=30,
        )


# ===========================================================================
# ENTRY POINT
# ===========================================================================

def main():
    linha()
    print("  AUTOMAÇÃO DE VÍDEOS")
    linha()

    # Sincroniza uma vez logo no início (primeiro ciclo imediato)
    sincronizar_credenciais_humble()

    config = exibir_menu()

    # -------------------------------------------------------------------
    # NOVO — deriva para anúncios se o menu retornou modo_operacao=anuncios
    # -------------------------------------------------------------------
    if config.get("modo_operacao") == "anuncios":
        print("\nMODO ANÚNCIOS — Sistema iniciado. Ctrl+C para encerrar.")
        try:
            executar_anuncios(config)
        except KeyboardInterrupt:
            print("\nEncerrado pelo usuário.")
        return

    # -------------------------------------------------------------------
    # ORIGINAL — fluxo de conteúdo orgânico (sem alteração)
    # -------------------------------------------------------------------
    modo = config["modo"]
    ciclo_num = 0

    if modo == "unico":
        ciclo_num = 1
        print(f"\nCICLO {ciclo_num} — Iniciando execução única...")
        executar_ciclo(config)
        print("Execução única concluída.")
    else:
        print("\nMODO CONTÍNUO — Sistema iniciado. Pressione Ctrl+C para encerrar.")
        print(
            "Horários de publicação: "
            + " | ".join(f"{h:02d}:00" for h in [9, 12, 17, 19, 21])
        )
        try:
            while True:
                ciclo_num += 1
                print(
                    f"\nCICLO {ciclo_num} — "
                    f"{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
                )
                executar_ciclo(config)
                print(f"  Ciclo {ciclo_num} concluído.")
                aguardar_proxima_janela()
        except KeyboardInterrupt:
            print(f"\nEncerrado pelo usuário após {ciclo_num} ciclos. Até a próxima!")



if __name__ == "__main__":
    main()