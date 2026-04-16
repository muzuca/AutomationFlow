"""
arquivo: conteudo/personas/__init__.py
descrição: Auto-discovery de personas. Basta criar um arquivo .py nesta pasta para que ele apareça no menu automaticamente.
"""

import importlib
from pathlib import Path

# Localiza a pasta atual (conteudo/personas)
_pasta = Path(__file__).parent
_PERSONAS: dict = {}

# Varre os arquivos .py para registro automático
for _arq in sorted(_pasta.glob("*.py")):
    if _arq.name.startswith("_"):
        continue
    
    # Ajuste no caminho do import para a nova estrutura de pastas
    # O sistema agora identifica como 'personas.nome_do_arquivo'
    try:
        _mod = importlib.import_module(f"conteudo.personas.{_arq.stem}")
        
        # Validação da Interface Obrigatória
        for _attr in ("ID", "NOME", "CENAS_PADRAO", "USA_SIGNOS", "SIGNOS", "TEMAS", "gerar_roteiro"):
            if not hasattr(_mod, _attr):
                raise ImportError(f"Persona '{_arq.name}' está faltando o atributo obrigatório: {_attr}")
        
        _PERSONAS[_mod.ID] = _mod
    except Exception as e:
        print(f"  ❌ Erro ao carregar persona '{_arq.name}': {e}")

def listar() -> list[str]:
    """Retorna lista de IDs das personas disponíveis."""
    return list(_PERSONAS.keys())

def obter(personagem_id: str):
    """Retorna o módulo da persona pelo ID."""
    if personagem_id not in _PERSONAS:
        raise ValueError(f"Persona não encontrada: {personagem_id!r}")
    return _PERSONAS[personagem_id]

def nomes() -> dict[str, str]:
    """Retorna dicionário {ID: NOME} para exibição no menu."""
    return {pid: mod.NOME for pid, mod in _PERSONAS.items()}