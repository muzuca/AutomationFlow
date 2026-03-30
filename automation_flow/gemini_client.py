import os
import time
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")


def _criar_cliente() -> genai.Client:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY não definida no arquivo .env")
    return genai.Client(api_key=GEMINI_API_KEY)


def gerar_prompt_video(
    personagem: str,
    cenario: str,
    tipo_mensagem: str,
    idioma: str = "pt-BR",
    duracao_segundos: int = 8,
) -> str:
    """
    Chama o Gemini para gerar um prompt cinematográfico de vídeo
    com base em personagem, cenário e tipo de mensagem.

    Retorna o prompt como string pronto para enviar ao Flow.
    """
    cliente = _criar_cliente()

    instrucao_sistema = (
        "Você é um especialista em criação de prompts para geração de vídeos com IA. "
        "Seu objetivo é criar prompts cinematográficos, detalhados e visualmente ricos "
        "para o Google Flow (Veo 3.1). "
        "O prompt deve descrever a cena de forma objetiva, em uma única frase ou parágrafo curto, "
        "sem usar aspas, sem explicações adicionais, apenas o prompt em si. "
        f"Responda sempre em {idioma}."
    )

    mensagem_usuario = (
        f"Crie um prompt de vídeo com as seguintes características:\n"
        f"- Personagem: {personagem}\n"
        f"- Cenário: {cenario}\n"
        f"- Tipo de mensagem/emoção: {tipo_mensagem}\n"
        f"- Duração aproximada: {duracao_segundos} segundos\n"
        f"- Formato: vertical 9:16 (estilo Reels/TikTok)\n\n"
        f"Retorne APENAS o prompt, sem introdução, sem explicação, sem aspas."
    )

    print(f"\n[GEMINI] Gerando prompt para:")
    print(f"  Personagem: {personagem}")
    print(f"  Cenário:    {cenario}")
    print(f"  Mensagem:   {tipo_mensagem}")

    for tentativa in range(1, 4):
        try:
            resposta = cliente.models.generate_content(
                model=GEMINI_MODEL,
                contents=mensagem_usuario,
                config=types.GenerateContentConfig(
                    system_instruction=instrucao_sistema,
                    temperature=0.85,
                    max_output_tokens=300,
                ),
            )
            prompt = resposta.text.strip().strip('"').strip("'")
            print(f"  ✔ Prompt gerado: {prompt!r}")
            return prompt
        except Exception as e:
            print(f"  ⚠ Tentativa {tentativa}/3 falhou: {e}")
            if tentativa < 3:
                time.sleep(3)

    raise RuntimeError("Não foi possível gerar o prompt via Gemini após 3 tentativas.")


def gerar_lote_prompts(
    personagem: str,
    cenario: str,
    tipos_mensagem: list[str],
    idioma: str = "pt-BR",
    duracao_segundos: int = 8,
) -> list[str]:
    """
    Gera um prompt para cada tipo de mensagem da lista.
    Retorna lista de prompts na mesma ordem.
    """
    prompts = []
    for tipo in tipos_mensagem:
        prompt = gerar_prompt_video(
            personagem=personagem,
            cenario=cenario,
            tipo_mensagem=tipo,
            idioma=idioma,
            duracao_segundos=duracao_segundos,
        )
        prompts.append(prompt)
        time.sleep(1)  # respeita rate limit da API
    return prompts