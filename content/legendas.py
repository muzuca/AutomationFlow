# content/legendas.py — Gestão de legendas por personagem
# Cada personagem tem um legendas.txt no seu diretório de destino.
# Formato:
#   === NomeDoArquivo.mp4 ===
#   Descrição do vídeo
#   #hashtag1 #hashtag2 #hashtag3
#
# Quando um vídeo é apagado do diretório, a legenda correspondente é removida.

from __future__ import annotations

import re
from pathlib import Path


def salvar_legenda(
    pasta_destino: Path,
    nome_video: str,
    descricao: str,
    hashtags: list[str] | None = None,
) -> None:
    """Adiciona ou atualiza a legenda de um vídeo no legendas.txt do personagem.
    
    Args:
        pasta_destino: Diretório do personagem (ex: G:/Meu Drive/Videos/AnaCartomante/)
        nome_video: Nome do arquivo de vídeo (ex: AnaCartomante_Gemeos_signos_20260508.mp4)
        descricao: Caption/descrição gerada pelo Gemini
        hashtags: Lista de hashtags (ex: ["#tarot", "#signos"])
    """
    legendas_path = pasta_destino / "legendas.txt"
    marcador = f"=== {nome_video} ==="
    
    # Monta o bloco da legenda
    tags_str = " ".join(hashtags) if hashtags else ""
    bloco = f"{marcador}\n{descricao.strip()}\n{tags_str}\n"
    
    # Se o arquivo já existe, verifica se já tem esse vídeo
    if legendas_path.exists():
        conteudo = legendas_path.read_text(encoding="utf-8")
        
        # Substitui bloco existente (se o vídeo foi re-gerado)
        if marcador in conteudo:
            padrao = re.escape(marcador) + r".*?(?=\n=== |\Z)"
            conteudo = re.sub(padrao, bloco.strip(), conteudo, flags=re.DOTALL)
            legendas_path.write_text(conteudo.strip() + "\n\n", encoding="utf-8")
            return
        
        # Anexa no final
        conteudo = conteudo.strip() + "\n\n" + bloco
        legendas_path.write_text(conteudo.strip() + "\n\n", encoding="utf-8")
    else:
        pasta_destino.mkdir(parents=True, exist_ok=True)
        legendas_path.write_text(bloco.strip() + "\n\n", encoding="utf-8")


def limpar_legendas_orfas(pasta_destino: Path) -> int:
    """Remove do legendas.txt as entradas cujo vídeo não existe mais no diretório.
    
    Chamado no início de cada ciclo para manter o arquivo sincronizado.
    
    Returns:
        Número de entradas removidas.
    """
    legendas_path = pasta_destino / "legendas.txt"
    
    if not legendas_path.exists():
        return 0
    
    conteudo = legendas_path.read_text(encoding="utf-8")
    
    # Extrai todos os blocos
    blocos = re.split(r"(?=^=== .+\.mp4 ===)", conteudo, flags=re.MULTILINE)
    
    mantidos = []
    removidos = 0
    
    for bloco in blocos:
        bloco = bloco.strip()
        if not bloco:
            continue
        
        # Extrai o nome do vídeo do marcador
        match = re.match(r"^=== (.+\.mp4) ===$", bloco, re.MULTILINE)
        if not match:
            # Bloco sem marcador válido — mantém (pode ser cabeçalho)
            mantidos.append(bloco)
            continue
        
        nome_video = match.group(1)
        video_path = pasta_destino / nome_video
        
        if video_path.exists():
            mantidos.append(bloco)
        else:
            removidos += 1
    
    if removidos > 0:
        novo_conteudo = "\n\n".join(mantidos).strip() + "\n\n" if mantidos else ""
        legendas_path.write_text(novo_conteudo, encoding="utf-8")
    
    return removidos
