"""
Auto-discovery de personas.
Basta criar um arquivo .py em conteudo/personas/ que ele aparece no menu automaticamente.

Interface obrigatória em cada persona.py:
  ID, NOME, CENAS_PADRAO, USA_SIGNOS, SIGNOS, TEMAS,
  tema_exige_signo(tema) -> bool
  fallback_mensagem(tema) -> str
  gerar_roteiro(tema, mensagem_central, signo, n_cenas) -> dict
"""
import importlib
from pathlib import Path

_pasta = Path(__file__).parent
_PERSONAS: dict = {}

for _arq in sorted(_pasta.glob("*.py")):
    if _arq.name.startswith("_"):
        continue
    _mod = importlib.import_module(f"automation_flow.flows.content.personas.{_arq.stem}")
    for _attr in ("ID", "NOME", "CENAS_PADRAO", "USA_SIGNOS", "SIGNOS", "TEMAS", "gerar_roteiro"):
        if not hasattr(_mod, _attr):
            raise ImportError(f"Persona '{_arq.name}' está faltando: {_attr}")
    _PERSONAS[_mod.ID] = _mod


def listar() -> list[str]:
    return list(_PERSONAS.keys())


def obter(personagem_id: str):
    if personagem_id not in _PERSONAS:
        raise ValueError(f"Persona não encontrada: {personagem_id!r}")
    return _PERSONAS[personagem_id]


def nomes() -> dict[str, str]:
    return {pid: mod.NOME for pid, mod in _PERSONAS.items()}