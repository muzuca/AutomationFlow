import json
import re
import time
from typing import Dict, List, Any, Callable, Optional

from automation_flow.core.clients.gemini_client import gerar_com_rotacao_json


def contar_palavras(texto: str) -> int:
    """
    Conta PALAVRAS RELEVANTES no diálogo:
      - ignora palavras com 1 ou 2 caracteres (ex: 'a', 'é', 'de', 'da')
      - texto vazio -> 0
    """
    if not texto:
        return 0

    palavras = (texto or "").split()
    n = 0
    for p in palavras:
        limpa = "".join(ch for ch in p.lower() if ch.isalpha())
        if len(limpa) <= 2:
            continue
        n += 1
    return n


def _parse_json_seguro(texto: str) -> dict:
    """
    Tenta fazer o parse de JSON, corrigindo pequenos desequilíbrios
    de chaves/colchetes.
    """
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        pass

    texto_corrigido = texto or ""
    abertos_colchete = texto_corrigido.count("[") - texto_corrigido.count("]")
    abertos_chave = texto_corrigido.count("{") - texto_corrigido.count("}")

    for _ in range(max(0, abertos_colchete)):
        texto_corrigido += "]"
    for _ in range(max(0, abertos_chave)):
        texto_corrigido += "}"

    return json.loads(texto_corrigido)


def _extrair_json_de_texto(texto: str) -> str:
    """
    Tenta extrair o primeiro bloco JSON útil de uma string.
    """
    if not texto:
        return ""

    texto = texto.strip()

    inicio_obj = texto.find("{")
    inicio_arr = texto.find("[")

    candidatos = [x for x in [inicio_obj, inicio_arr] if x != -1]
    if not candidatos:
        return texto

    inicio = min(candidatos)
    return texto[inicio:].strip()


def _limpar_resposta(texto: Any) -> str:
    """
    Remove cercas de código ``` e prefixo 'json' quando presentes.
    Também tolera respostas estranhas vindas como lista/objeto.
    """
    if texto is None:
        return ""

    if isinstance(texto, list):
        texto = "\n".join(str(x) for x in texto if x is not None)
    elif not isinstance(texto, str):
        texto = str(texto)

    texto = texto.strip()

    if texto.startswith("```"):
        partes = texto.split("```")
        escolhido = None

        for p in partes:
            p = p.strip()
            if not p:
                continue

            if p.lower().startswith("json"):
                p = p[4:].strip()

            if p.startswith("{") or p.startswith("["):
                escolhido = p
                break

        if escolhido is not None:
            texto = escolhido
        else:
            # pega o primeiro bloco depois da primeira cerca
            texto = partes.strip() if len(partes) > 1 else texto

    if texto.lstrip().lower().startswith("json"):
        texto = texto.lstrip()[4:]

    texto = _extrair_json_de_texto(texto)
    return texto.strip()


def _montar_mensagem_usuario_com_feedback(
    mensagem_usuario_base: str,
    feedback_erro: Optional[str],
) -> str:
    """
    Insere feedback de erro diretamente na mensagem de usuário
    para a próxima tentativa (error reinsertion).
    """
    if not feedback_erro:
        return mensagem_usuario_base

    bloco_feedback = (
        "\n\nIMPORTANTE (CORREÇÃO DE ERROS DE TENTATIVAS ANTERIORES):\n"
        "A tentativa anterior apresentou os seguintes problemas, "
        "que DEVEM ser corrigidos agora:\n"
        f"{feedback_erro}\n"
        "Refaça o JSON COMPLETO, obedecendo rigorosamente todas as "
        "regras originais e as correções acima.\n"
    )
    return mensagem_usuario_base + bloco_feedback


def _extrair_dialogo_quebrado(texto: str) -> str:
    """
    Fallback para respostas locais malformadas.
    Tenta recuperar o valor de "dialogo" mesmo se o JSON vier com string quebrada.
    """
    if not texto:
        return ""

    texto = texto.strip()

    m = re.search(r'"dialogo"\s*:\s*"(.*)', texto, re.DOTALL)
    if not m:
        return ""

    resto = m.group(1)

    cortes = [
        '\n"',
        '",\n',
        '",\r\n',
        '", "',
        '","',
        '"}',
        '",}',
    ]

    fim = None
    for marcador in cortes:
        idx = resto.find(marcador)
        if idx != -1:
            if fim is None or idx < fim:
                fim = idx

    if fim is not None:
        resto = resto[:fim]

    resto = resto.strip()
    resto = resto.replace('\\"', '"')
    resto = resto.replace("\\n", " ")
    resto = resto.replace("\\r", " ")
    resto = " ".join(resto.split())
    return resto


def _parse_resposta_dialogo_local(texto_bruto: Any) -> str:
    """
    Primeiro tenta parsear JSON normal.
    Se falhar por JSON malformado, tenta extrair só o campo 'dialogo'.
    """
    texto_limpo = _limpar_resposta(texto_bruto)

    try:
        dados = _parse_json_seguro(texto_limpo)
        if isinstance(dados, dict):
            dialogo = (dados.get("dialogo", "") or "").strip()
            if dialogo:
                return dialogo
    except Exception:
        pass

    dialogo_fallback = _extrair_dialogo_quebrado(texto_limpo)
    if dialogo_fallback:
        return dialogo_fallback

    raise ValueError("Não foi possível extrair o campo 'dialogo' da resposta local.")


def _corrigir_dialogo_cena_isolada(
    instrucao_sistema: str,
    mensagem_usuario_base: str,
    cena_base: dict,
    cena_atual: dict,
    min_palavras: int,
    max_palavras: int,
) -> str:
    """
    Pede AO MODELO apenas a reescrita do diálogo de UMA cena.
    Se falhar, devolve o diálogo original.
    """
    dialogo_atual = (cena_atual.get("dialogo", "") or "").strip()
    n_atual = contar_palavras(dialogo_atual)

    print(
        f"  ↻ Reescrevendo apenas a cena {cena_atual.get('numero', '?')} "
        f"({cena_atual.get('nome', '?')}) — diálogo atual com {n_atual} palavras relevantes."
    )

    mensagem_cena = (
        f"{mensagem_usuario_base}\n\n"
        "AGORA, REESCREVA APENAS UMA CENA ESPECÍFICA.\n"
        f"- Número da cena: {cena_atual.get('numero', '?')}\n"
        f"- Nome da cena: {cena_atual.get('nome', '?')}\n"
        f"- Objetivo da cena: {cena_base.get('objetivo', '')}\n\n"
        "DIÁLOGO ANTERIOR (NÃO COPIE, REESCREVA MELHOR):\n"
        f"{dialogo_atual}\n\n"
        "REGRAS OBRIGATÓRIAS:\n"
        "- Reescreva somente o campo dialogo.\n"
        "- Mantenha o mesmo sentido, a mesma intenção e o mesmo momento narrativo.\n"
        "- Use UMA única frase contínua.\n"
        "- Não use markdown.\n"
        f"- O diálogo deve ficar entre {min_palavras} e {max_palavras} palavras RELEVANTES.\n"
        f"- Se ficar com menos de {min_palavras} palavras relevantes, a resposta será rejeitada.\n"
        f"- Se ficar com mais de {max_palavras} palavras relevantes, a resposta será rejeitada.\n"
        "- Soe natural, humano e falável.\n\n"
        "RETORNE EXATAMENTE NESTE FORMATO JSON:\n"
        "{\n"
        '  \"dialogo\": \"texto aqui\"\n'
        "}"
    )

    tentativas_locais = 2
    ultimo_texto_bruto = ""

    for tentativa in range(1, tentativas_locais + 1):
        try:
            print("\n" + "=" * 90)
            print("[DEBUG][CORRECAO_LOCAL] PROMPT ENVIADO AO GEMINI")
            print("=" * 90)
            print(
                f"[DEBUG][CORRECAO_LOCAL] Tentativa local: {tentativa}/{tentativas_locais}"
            )
            print(
                f"[DEBUG][CORRECAO_LOCAL] Cena: {cena_atual.get('numero', '?')} - {cena_atual.get('nome', '?')}"
            )
            print(
                f"[DEBUG][CORRECAO_LOCAL] Faixa alvo: {min_palavras}-{max_palavras} palavras relevantes"
            )
            print("-" * 90)
            print("[DEBUG][CORRECAO_LOCAL] INSTRUCAO_SISTEMA:")
            print(instrucao_sistema)
            print("-" * 90)
            print("[DEBUG][CORRECAO_LOCAL] MENSAGEM_USUARIO:")
            print(mensagem_cena)
            print("=" * 90 + "\n")

            ultimo_texto_bruto = gerar_com_rotacao_json(
                mensagem_usuario=mensagem_cena,
                instrucao_sistema=instrucao_sistema,
                max_output_tokens=512,
                temperature=0.6,
            )

            print("\n" + "=" * 90)
            print("[DEBUG][CORRECAO_LOCAL] RESPOSTA BRUTA DO GEMINI")
            print("=" * 90)
            print(ultimo_texto_bruto)
            print("=" * 90 + "\n")

            novo_dialogo = _parse_resposta_dialogo_local(ultimo_texto_bruto)

            if not novo_dialogo:
                raise ValueError("Resposta local sem campo 'dialogo' válido.")

            n_novo = contar_palavras(novo_dialogo)

            print("\n" + "=" * 90)
            print("[DEBUG][CORRECAO_LOCAL] DIALOGO EXTRAIDO")
            print("=" * 90)
            print(novo_dialogo)
            print(f"[DEBUG][CORRECAO_LOCAL] Palavras relevantes: {n_novo}")
            print("=" * 90 + "\n")

            if n_novo < min_palavras:
                if n_novo <= max(3, min_palavras // 2):
                    raise ValueError(
                        f"Correção local muito curta ({n_novo} palavras); abortando correção local."
                    )
                raise ValueError(
                    f"Correção local ainda abaixo da faixa: {n_novo} palavras."
                )

            if n_novo > max_palavras:
                raise ValueError(
                    f"Correção local ainda acima da faixa: {n_novo} palavras."
                )

            print(
                f"  ✔ Cena {cena_atual.get('numero', '?')} ajustada localmente "
                f"para {n_novo} palavras relevantes."
            )
            return novo_dialogo

        except Exception as e:
            print(
                f"  ⚠ Falha ao corrigir cena {cena_atual.get('numero', '?')} "
                f"({cena_atual.get('nome', '?')}): {e}"
            )

            if "muito curta" in str(e).lower():
                break

            if tentativa < tentativas_locais:
                time.sleep(1)

    print(
        f"  ⚠ Não foi possível corrigir a cena {cena_atual.get('numero', '?')} "
        f"localmente; mantendo diálogo original."
    )
    return dialogo_atual


def gerar_roteiro_generico(
    instrucao_sistema: str,
    mensagem_usuario: str,
    estrutura_cenas: List[dict],
    n_cenas: int,
    builder_prompt_veo3: Callable[[dict, str], str],
    validar_dialogos: Callable[[List[dict]], List[str]] | None = None,
    min_palavras: int = 14,
    max_palavras: int = 25,
) -> Dict[str, Any]:
    """
    Motor genérico de geração de roteiro.

    Fluxo:
      1. Gera JSON completo
      2. Faz parse seguro
      3. Valida diálogos
      4. Se houver cenas fora da faixa, tenta corrigir APENAS essas cenas
      5. Se, após tentativa de correção local, AINDA houver cenas fora da faixa,
         pede novo JSON completo (exceto se erro for claramente externo, ex: 429)
      6. Monta prompts Veo3
    """
    if n_cenas < 1:
        raise ValueError("n_cenas deve ser pelo menos 1.")
    if n_cenas > len(estrutura_cenas):
        raise ValueError(f"n_cenas máximo suportado é {len(estrutura_cenas)}.")

    tentativas = 6
    ultimo_erro_feedback: Optional[str] = None

    for tentativa in range(1, tentativas + 1):
        texto_bruto = ""
        erro_externo = False  # ex: 429/RESOURCE_EXHAUSTED

        try:
            mensagem_com_feedback = _montar_mensagem_usuario_com_feedback(
                mensagem_usuario_base=mensagem_usuario,
                feedback_erro=ultimo_erro_feedback,
            )

            texto_bruto = gerar_com_rotacao_json(
                mensagem_usuario=mensagem_com_feedback,
                instrucao_sistema=instrucao_sistema,
                max_output_tokens=4096,
                temperature=0.9,
            )

            texto = _limpar_resposta(texto_bruto)
            dados = _parse_json_seguro(texto)

            if not isinstance(dados, dict):
                raise ValueError("Resposta do modelo não retornou um objeto JSON válido.")

            if "cenas" not in dados or not isinstance(dados["cenas"], list):
                raise ValueError(
                    "JSON retornado não contém a chave 'cenas' em formato de lista."
                )

            cenas_json = dados["cenas"][:n_cenas]

            if len(cenas_json) < n_cenas:
                raise ValueError(
                    f"Modelo retornou apenas {len(cenas_json)} cenas, "
                    f"mas eram esperadas {n_cenas}."
                )

            for i, cena_dados in enumerate(cenas_json):
                if not isinstance(cena_dados, dict):
                    raise ValueError(f"Cena {i + 1} não é um objeto JSON válido.")
                if "dialogo" not in cena_dados:
                    raise ValueError(f"Cena {i + 1} não contém campo 'dialogo'.")

            avisos_antes: List[str] = []
            if validar_dialogos:
                try:
                    avisos_antes = validar_dialogos(cenas_json) or []
                except ValueError as e:
                    print(
                        f"  ⚠ Validação inicial detectou cenas fora da margem "
                        f"na tentativa {tentativa}/{tentativas}: {e}"
                    )
                    avisos_antes = [str(e)]

            cenas_corrigidas = 0

            # LOG de todas as cenas + correções locais
            for idx, cena in enumerate(cenas_json):
                dialogo = (cena.get("dialogo", "") or "").strip()
                n_pal = contar_palavras(dialogo)

                print(
                    f"[DEBUG] Cena {idx + 1} "
                    f"({cena.get('nome', estrutura_cenas[idx].get('nome', '?'))}) "
                    f"- {n_pal} palavras: {dialogo}"
                )

                if n_pal < min_palavras or n_pal > max_palavras:
                    cena_base = estrutura_cenas[idx]
                    novo_dialogo = _corrigir_dialogo_cena_isolada(
                        instrucao_sistema=instrucao_sistema,
                        mensagem_usuario_base=mensagem_usuario,
                        cena_base=cena_base,
                        cena_atual=cena,
                        min_palavras=min_palavras,
                        max_palavras=max_palavras,
                    )
                    if novo_dialogo != dialogo:
                        cena["dialogo"] = novo_dialogo
                        cenas_corrigidas += 1

            avisos_finais: List[str] = []
            erro_final = None

            if validar_dialogos:
                try:
                    avisos_finais = validar_dialogos(cenas_json) or []
                except ValueError as e:
                    erro_final = e

            # Se ainda assim temos erro de faixa, decide se vale tentar de novo
            if erro_final:
                print(
                    f"  ⚠ Validação de diálogos falhou na tentativa "
                    f"{tentativa}/{tentativas}: {erro_final}"
                )
                for aviso in avisos_finais:
                    print(aviso)

                ultimo_erro_feedback = (
                    "Atenção: a resposta anterior foi rejeitada porque uma ou mais cenas "
                    "continuaram fora da faixa de tamanho exigida.\n"
                    f"- Cada diálogo deve ficar entre {min_palavras} e {max_palavras} palavras relevantes.\n"
                    "- Reescreva TODAS as cenas do zero de forma natural.\n"
                    "- Não corte bruscamente frases.\n"
                    "- Retorne JSON puro e válido.\n"
                )

                if tentativa < tentativas:
                    print("  ↻ Solicitando nova versão completa ao modelo...")
                    time.sleep(2)
                    continue

                raise RuntimeError(
                    "O modelo não conseguiu gerar diálogos válidos após várias tentativas."
                )

            # Se chegou aqui, tudo validado (mesmo que tenha passado por correção local)
            prompts: List[str] = []
            dialogos: List[str] = []
            textos_tela: List[str] = []

            for i, cena_dados in enumerate(cenas_json):
                if i >= len(estrutura_cenas):
                    raise ValueError(
                        "Modelo retornou mais cenas do que o esperado: "
                        f"índice {i}, n_cenas={n_cenas}."
                    )

                cena_base = estrutura_cenas[i]
                dialogo = (cena_dados.get("dialogo", "") or "").strip()
                texto_tela = (cena_dados.get("texto_tela", "") or "").strip()

                prompt_completo = builder_prompt_veo3(cena_base, dialogo)
                prompts.append(prompt_completo)
                dialogos.append(dialogo)
                textos_tela.append(texto_tela)

                print(
                    f"  ✔ Cena {i + 1} — {cena_base['nome']}: {texto_tela}\n"
                    f"     Diálogo ({contar_palavras(dialogo)} palavras relevantes): {dialogo}"
                )

            print(f"\n  📝 Descrição: {dados.get('descricao', '')}")
            print(f"  🏷  Hashtags: {' '.join(dados.get('hashtags', []))}")

            if cenas_corrigidas:
                print(f"  🔧 Cenas corrigidas localmente nesta tentativa: {cenas_corrigidas}")

            return {
                "prompts": prompts,
                "dialogos": dialogos,
                "textos_tela": textos_tela,
                "descricao": dados.get("descricao", ""),
                "hashtags": dados.get("hashtags", []),
                "cenas": cenas_json,
            }

        except json.JSONDecodeError as e:
            print(f"  ⚠ Tentativa {tentativa}/{tentativas} — JSON inválido: {e}")
            print(f"  ℹ Início da resposta: {str(texto_bruto)[:200]!r}")

            ultimo_erro_feedback = (
                "Atenção: o JSON retornado estava INVÁLIDO e não pôde ser parseado.\n"
                "- Retorne apenas JSON puro, sem markdown e sem texto fora das chaves.\n"
                "- Verifique vírgulas sobrando, aspas incorretas e "
                "chaves/colchetes desbalanceados."
            )

            if tentativa < tentativas:
                time.sleep(3)

        except Exception as e:
            msg = str(e)
            print(f"  ⚠ Tentativa {tentativa}/{tentativas} falhou: {msg}")

            # Heurística simples pra erro externo (ex.: quota/429 vindo encapsulado)
            if "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower():
                erro_externo = True

            ultimo_erro_feedback = (
                "Atenção: a resposta anterior apresentou erro ao ser processada.\n"
                f"- Erro interno capturado: {e}\n"
                f"- Cada diálogo deve permanecer entre {min_palavras} e {max_palavras} palavras relevantes.\n"
                "- Revise o JSON e mantenha a estrutura exatamente como pedida."
            )

            if tentativa < tentativas:
                # Se o erro parece externo (quota, rede etc.), não adianta
                # ficar “educando” o modelo com feedback; só espera e tenta de novo.
                if erro_externo:
                    time.sleep(5)
                else:
                    time.sleep(3)

    raise RuntimeError("Não foi possível gerar o roteiro após várias tentativas.")