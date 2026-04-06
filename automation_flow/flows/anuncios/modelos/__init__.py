# automation_flow/flows/anuncios/modelos/__init__.py

from automation_flow.flows.anuncios.modelos.ana_indica import AnaIndica
from automation_flow.flows.anuncios.modelos.lara_select import LaraSelect

_REGISTRO: dict[str, object] = {
    "ana_indica": AnaIndica,
    "lara_select": LaraSelect,
}


def listar() -> list[str]:
    return list(_REGISTRO.keys())


def nomes() -> dict[str, str]:
    return {slug: cls.NOME for slug, cls in _REGISTRO.items()}


def obter(slug: str):
    if slug not in _REGISTRO:
        raise ValueError(f"Modelo de anúncio desconhecida: {slug!r}")
    return _REGISTRO[slug]