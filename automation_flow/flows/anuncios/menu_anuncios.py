# automation_flow/flows/anuncios/menu_anuncios.py
from datetime import datetime
from automation_flow.flows.anuncios import modelos as modelos_reg
from automation_flow.flows.anuncios.tipos_filmagem import EXTENSOES_IMAGEM, listar as listar_tipos
from automation_flow.flows.anuncios.watcher import garantir_estrutura


def linha(char="=", largura=52):
    print(char * largura)


def _contar_pendentes() -> dict[str, dict[str, int]]:
    resultado = {}
    for slug in modelos_reg.listar():
        modelo = modelos_reg.obter(slug)
        resultado[slug] = {}
        for tipo in listar_tipos():
            dir_pendente = modelo.dir_tipo(tipo) / "pendente"
            if not dir_pendente.exists():
                resultado[slug][tipo] = 0
                continue
            # Conta pastas que contenham pelo menos uma imagem
            resultado[slug][tipo] = sum(
                1 for item in dir_pendente.iterdir()
                if item.is_dir()
                and any(
                    f.suffix.lower() in EXTENSOES_IMAGEM
                    for f in item.iterdir()
                    if f.is_file()
                )
            )
    return resultado

def _exibir_painel_pendentes(pendentes: dict[str, dict[str, int]]) -> int:
    """Exibe o painel de pendentes e retorna o total geral."""
    nms = modelos_reg.nomes()
    total_geral = 0

    print()
    for slug, tipos in pendentes.items():
        total_modelo = sum(tipos.values())
        total_geral += total_modelo
        status = f"{total_modelo} imagem(ns) pendente(s)" if total_modelo else "nenhuma pendente"
        print(f"  📁 {nms[slug]}  —  {status}")
        for tipo, qtd in tipos.items():
            if qtd > 0:
                icone = "🖼 "
                print(f"       {icone}{tipo}: {qtd}")
    print()
    return total_geral


def exibir_menu_anuncios() -> dict:
    linha()
    print(f"  ANÚNCIOS DE PRODUTOS — TIKTOK SHOP")
    print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    linha()

    # Garante estrutura de diretórios antes de qualquer coisa
    garantir_estrutura()

    # Lê o que há pendente agora
    pendentes = _contar_pendentes()
    total = _exibir_painel_pendentes(pendentes)

    if total == 0:
        print("  ℹ  Nenhuma imagem pendente nos diretórios monitorados.")
        print("     Coloque imagens em:")
        nms = modelos_reg.nomes()
        for slug in modelos_reg.listar():
            modelo = modelos_reg.obter(slug)
            for tipo in listar_tipos():
                print(f"     {modelo.dir_tipo(tipo) / 'pendente'}")
        print()

    # Única pergunta: modo de execução
    linha("-", 52)
    print("  MODO DE EXECUÇÃO")
    print("  1. Processar tudo que está pendente agora e encerrar")
    print("  2. Monitorar continuamente — processa conforme chegam novas imagens  [padrão]")
    print()

    while True:
        entrada = input("  Modo [1/2] [2]: ").strip()
        if not entrada or entrada == "2":
            modo = "continuo"
            print("  ✔ Modo: Monitorar continuamente")
            break
        if entrada == "1":
            modo = "unico"
            print("  ✔ Modo: Processar pendentes e encerrar")
            break
        print("  Digite 1 ou 2.")

    print()
    linha("-", 52)
    print(f"  Imagens pendentes agora:  {total}")
    print(f"  Modo:                     {'Monitor contínuo' if modo == 'continuo' else 'Processar e encerrar'}")
    linha("-", 52)
    print()

    return {
        "modo_operacao": "anuncios",
        "modo": modo,
        # Passa None = todos os modelos e tipos que tiverem pendentes
        "modelos": None,
        "tipos_filmagem": None,
    }