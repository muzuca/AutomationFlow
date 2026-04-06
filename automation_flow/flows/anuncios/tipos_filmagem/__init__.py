# automation_flow/flows/anuncios/tipos_filmagem/__init__.py

# Mapeamento slug → metadados de cada tipo de filmagem.
# Usado pelo watcher para validar diretórios e pelo menu para exibir descrições.

TIPOS: dict[str, dict] = {
    "POV-Maos": {
        "nome": "POV Mãos",
        "descricao": "Câmera de cima, mãos segurando o produto sobre superfície",
        "precisa_modelo": False,   # só as mãos, sem foto da modelo
        "precisa_imagem_produto": True,
    },
    "ModeloFrontal": {
        "nome": "Modelo Frontal (Talking Head)",
        "descricao": "Modelo de frente, falando para a câmera, segurando ou usando o produto",
        "precisa_modelo": True,
        "precisa_imagem_produto": True,
    },
    "ModeloPes": {
        "nome": "Modelo — Pés / Calçados",
        "descricao": "Somente pés/pernas da modelo usando o produto (calçados, meias, tornozeleiras)",
        "precisa_modelo": False,
        "precisa_imagem_produto": True,
    },
    "ModeloCaminhando": {
        "nome": "Modelo Caminhando",
        "descricao": "Modelo caminhando usando o produto (bolsa, roupa, acessório)",
        "precisa_modelo": True,
        "precisa_imagem_produto": True,
    },
    "ProdutoFlat": {
        "nome": "Flat Lay (Produto Sozinho)",
        "descricao": "Produto sobre superfície bonita, sem modelo, foco nos detalhes",
        "precisa_modelo": False,
        "precisa_imagem_produto": True,
    },
}

EXTENSOES_IMAGEM = {".jpg", ".jpeg", ".png", ".webp"}


def listar() -> list[str]:
    return list(TIPOS.keys())


def obter(slug: str) -> dict:
    if slug not in TIPOS:
        raise ValueError(f"Tipo de filmagem desconhecido: {slug!r}")
    return TIPOS[slug]