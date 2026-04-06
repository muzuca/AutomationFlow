# automation_flow/flows/anuncios/watcher.py
"""
Monitora os diretórios de produtos e detecta novos anúncios pendentes.

Estrutura esperada:
  <DIR_BASE>/<Modelo>/<TipoFilmagem>/pendente/<N>/   ← pasta numérica com imagens
  <DIR_BASE>/<Modelo>/<TipoFilmagem>/processando/<N>/
  <DIR_BASE>/<Modelo>/<TipoFilmagem>/concluido/<N>/
"""
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from automation_flow.flows.anuncios import modelos as modelos_reg
from automation_flow.flows.anuncios.tipos_filmagem import (
    EXTENSOES_IMAGEM,
    listar as listar_tipos,
)

_SUBDIRS = ("pendente", "processando", "concluido")


def _log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WATCHER] {msg}")


# ---------------------------------------------------------------------------
# Estrutura de uma tarefa detectada
# ---------------------------------------------------------------------------
@dataclass
class TarefaAnuncio:
    modelo_slug: str        # "lara_select"
    modelo_nome: str        # "LaraSelect"
    tipo_filmagem: str      # "ModeloFrontal"
    id_anuncio: str         # "1", "2", "42" — nome da pasta numérica
    dir_anuncio: Path       # path completo dentro de processando/<N>/
    imagens: list[Path]     # todos os arquivos de imagem dentro da pasta
    dir_concluido: Path     # onde mover quando terminar

    @property
    def nome_produto(self) -> str:
        """
        Usa o nome do primeiro arquivo de imagem como identificador do produto.
        Ex: "tenis-chunky-branco.jpg" → "tenis-chunky-branco"
        Se o arquivo não tiver nome descritivo, usa o id do anúncio.
        """
        for img in self.imagens:
            if img.stem and not img.stem.isdigit():
                return img.stem
        return f"anuncio-{self.id_anuncio}"

    def __str__(self):
        return (
            f"{self.modelo_nome} | {self.tipo_filmagem} | "
            f"anúncio #{self.id_anuncio} | {len(self.imagens)} imagem(ns) | "
            f"produto: {self.nome_produto}"
        )


# ---------------------------------------------------------------------------
# Inicialização dos diretórios
# ---------------------------------------------------------------------------
def garantir_estrutura(modelo_slug: str | None = None):
    """
    Cria pendente/processando/concluido para todos os tipos de filmagem
    de todos os modelos (ou só do modelo especificado).
    """
    slugs = [modelo_slug] if modelo_slug else modelos_reg.listar()
    tipos = listar_tipos()

    for slug in slugs:
        modelo = modelos_reg.obter(slug)
        for tipo in tipos:
            dir_tipo = modelo.dir_tipo(tipo)
            for sub in _SUBDIRS:
                (dir_tipo / sub).mkdir(parents=True, exist_ok=True)

    _log("Estrutura de diretórios verificada/criada.")


# ---------------------------------------------------------------------------
# Leitura de imagens dentro de uma pasta de anúncio
# ---------------------------------------------------------------------------
def _listar_imagens(dir_anuncio: Path) -> list[Path]:
    """Retorna todos os arquivos de imagem dentro de uma pasta de anúncio."""
    if not dir_anuncio.exists():
        return []
    return [
        f for f in sorted(dir_anuncio.iterdir())
        if f.is_file() and f.suffix.lower() in EXTENSOES_IMAGEM
    ]


# ---------------------------------------------------------------------------
# Varredura de pastas pendentes
# ---------------------------------------------------------------------------
def _escanear_pastas_pendentes(modelo_slug: str, tipo: str) -> list[Path]:
    """
    Retorna lista de subdiretórios numéricos dentro de pendente/
    que contenham pelo menos uma imagem.
    """
    modelo = modelos_reg.obter(modelo_slug)
    dir_pendente = modelo.dir_tipo(tipo) / "pendente"

    if not dir_pendente.exists():
        return []

    pastas = []
    for item in sorted(dir_pendente.iterdir(), key=lambda p: p.name):
        if not item.is_dir():
            continue
        # Aceita qualquer nome de pasta (numérico ou não)
        if _listar_imagens(item):
            pastas.append(item)

    return pastas


def _mover_para_processando(dir_anuncio: Path) -> Path:
    """Move a pasta do anúncio de pendente/ para processando/."""
    dir_processando = dir_anuncio.parent.parent / "processando" / dir_anuncio.name
    if dir_processando.exists():
        shutil.rmtree(dir_processando)
    shutil.move(str(dir_anuncio), str(dir_processando.parent))
    return dir_processando


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def coletar_tarefas(
    modelos_filtro: list[str] | None = None,
    tipos_filtro: list[str] | None = None,
) -> list[TarefaAnuncio]:
    """
    Varre todos os diretórios pendente/<N>/ e retorna lista de TarefaAnuncio.
    Move cada pasta encontrada para processando/ antes de retornar.
    """
    slugs = modelos_filtro or modelos_reg.listar()
    tipos = tipos_filtro or listar_tipos()
    tarefas: list[TarefaAnuncio] = []

    for slug in slugs:
        modelo = modelos_reg.obter(slug)
        for tipo in tipos:
            for pasta in _escanear_pastas_pendentes(slug, tipo):
                pasta_proc = _mover_para_processando(pasta)
                imagens = _listar_imagens(pasta_proc)
                dir_concluido = modelo.dir_tipo(tipo) / "concluido" / pasta.name
                dir_concluido.mkdir(parents=True, exist_ok=True)

                tarefa = TarefaAnuncio(
                    modelo_slug=slug,
                    modelo_nome=modelo.NOME,
                    tipo_filmagem=tipo,
                    id_anuncio=pasta.name,
                    dir_anuncio=pasta_proc,
                    imagens=imagens,
                    dir_concluido=dir_concluido,
                )
                _log(f"Tarefa detectada: {tarefa}")
                tarefas.append(tarefa)

    if not tarefas:
        _log("Nenhum anúncio pendente encontrado.")

    return tarefas


def devolver_para_pendente(tarefa: TarefaAnuncio):
    """Em caso de erro, move a pasta de volta para pendente/."""
    dir_pendente = tarefa.dir_anuncio.parent.parent / "pendente" / tarefa.id_anuncio
    if dir_pendente.exists():
        shutil.rmtree(dir_pendente)
    shutil.move(str(tarefa.dir_anuncio), str(dir_pendente.parent))
    _log(f"Anúncio #{tarefa.id_anuncio} devolvido para pendente/")


def marcar_concluido(tarefa: TarefaAnuncio, video_gerado: Path):
    """
    Move a pasta do anúncio (imagens originais) para concluido/.
    O vídeo gerado já deve estar salvo em dir_concluido pelo pipeline.
    """
    destino = tarefa.dir_anuncio.parent.parent / "concluido" / tarefa.id_anuncio
    if destino.exists():
        shutil.rmtree(destino)
    shutil.move(str(tarefa.dir_anuncio), str(destino.parent))
    _log(
        f"Anúncio #{tarefa.id_anuncio} concluído → "
        f"vídeo: {video_gerado.name}"
    )


# ---------------------------------------------------------------------------
# Modo monitor contínuo
# ---------------------------------------------------------------------------
def monitorar_loop(
    callback,
    modelos_filtro: list[str] | None = None,
    tipos_filtro: list[str] | None = None,
    intervalo_segundos: int = 30,
):
    """
    Fica em loop verificando por novas pastas a cada intervalo_segundos.
    Quando encontra, chama callback(tarefas).
    Interrompido por Ctrl+C.
    """
    _log(
        f"Monitor ativo — verificando a cada {intervalo_segundos}s. "
        f"Ctrl+C para encerrar."
    )
    try:
        while True:
            tarefas = coletar_tarefas(modelos_filtro, tipos_filtro)
            if tarefas:
                callback(tarefas)
            else:
                _log(
                    f"Nenhum anúncio pendente. "
                    f"Próxima verificação em {intervalo_segundos}s..."
                )
            time.sleep(intervalo_segundos)
    except KeyboardInterrupt:
        _log("Monitor encerrado pelo usuário.")