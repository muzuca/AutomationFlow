import json
import time
from typing import Dict, List, Any, Callable

from automation_flow.core.clients.gemini_client import gerar_com_rotacao_json


def _contar_palavras(texto: str) -> int:
    return len(texto.split())


def _parse_json_seguro(texto: str) -> dict:
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    texto_corrigido = texto
    abertos_colchete = texto.count("[") - texto.count("]")
    abertos_chave = texto.count("{") - texto.count("}")

    for _ in range(abertos_colchete):
        texto_corrigido += "]"
    for _ in range(abertos_chave):
        texto_corrigido += "}"

    return json.loads(texto_corrigido)


def _limpar_resposta(texto: str) -> str:
    texto = texto.strip()
    if texto.startswith("```"):
        partes = texto.split("```")
        texto = partes[1]
        if texto.startswith("json"):
            texto = texto[4:]
    return texto.strip()


def gerar_roteiro_generico(
    instrucao_sistema: str,
    mensagem_usuario: str,
    estrutura_cenas: List[dict],
    n_cenas: int,
    builder_prompt_veo3: Callable[[dict, str], str],
    validar_dialogos: Callable[[List[dict]], List[str]] | None = None,
) -> Dict[str, Any]:
    """
    Motor genérico de geração de roteiro:
      - chama Gemini
      - valida diálogos (opcional)
      - monta prompts Veo3 a partir da estrutura de cenas do personagem
    Retorna dict com: prompts, dialogos, textos_tela, descricao, hashtags.
    """
    if n_cenas < 1:
        raise ValueError("n_cenas deve ser pelo menos 1.")
    if n_cenas > len(estrutura_cenas):
        raise ValueError(f"n_cenas máximo suportado é {len(estrutura_cenas)}.")

    tentativas = 3
    for tentativa in range(1, tentativas + 1):
        try:
            texto_bruto = gerar_com_rotacao_json(
                mensagem_usuario=mensagem_usuario,
                instrucao_sistema=instrucao_sistema,
                max_output_tokens=4096,
                temperature=0.9,
            )

            texto = _limpar_resposta(texto_bruto)
            dados = _parse_json_seguro(texto)

            cenas_json = dados["cenas"][:n_cenas]

            if validar_dialogos:
                avisos = validar_dialogos(cenas_json)
                for aviso in avisos:
                    print(aviso)

            prompts: List[str] = []
            dialogos: List[str] = []
            textos_tela: List[str] = []

            for i, cena_dados in enumerate(cenas_json):
                cena_base = estrutura_cenas[i]
                dialogo = cena_dados["dialogo"]
                texto_tela = cena_dados.get("texto_tela", "")

                prompt_completo = builder_prompt_veo3(cena_base, dialogo)
                prompts.append(prompt_completo)
                dialogos.append(dialogo)
                textos_tela.append(texto_tela)

                print(
                    f"  ✔ Cena {i + 1} — {cena_base['nome']}: {texto_tela}\n"
                    f"     Diálogo ({_contar_palavras(dialogo)} palavras): {dialogo}"
                )

            print(f"\n  📝 Descrição: {dados.get('descricao', '')}")
            print(f"  🏷  Hashtags: {' '.join(dados.get('hashtags', []))}")

            return {
                "prompts": prompts,
                "dialogos": dialogos,
                "textos_tela": textos_tela,
                "descricao": dados.get("descricao", ""),
                "hashtags": dados.get("hashtags", []),
            }

        except json.JSONDecodeError as e:
            print(f"  ⚠ Tentativa {tentativa}/{tentativas} — JSON inválido: {e}")
            print(f"  ℹ Início da resposta: {texto_bruto[:200]!r}")
            if tentativa < tentativas:
                time.sleep(3)

        except Exception as e:
            print(f"  ⚠ Tentativa {tentativa}/{tentativas} falhou: {e}")
            if tentativa < tentativas:
                time.sleep(3)

    raise RuntimeError("Não foi possível gerar o roteiro após várias tentativas.")