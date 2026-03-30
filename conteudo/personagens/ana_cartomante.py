"""
Perfil fixo e completo da personagem Ana Cartomante.
Todos os blocos técnicos do prompt Veo 3 estão aqui centralizados.
Nunca altere este arquivo durante a geração — apenas entre roteiros.
"""

NOME = "Ana"
DESCRICAO_CURTA = "Ana Cartomante — cartomante brasileira, carisma Carioca, signos e tarot"

# ── Blocos fixos do prompt Veo 3 ────────────────────────────────────────────

CHARACTER_BLOCK = (
    "Character: Brazilian woman around 28 years old with light brown skin and golden "
    "undertones. Face: oval shape with soft cheekbones, straight nose, full lips with "
    "soft pink lipstick, long natural lashes, subtle brown eyeliner, thick softly arched "
    "brows, light-brown eyes with tiny amber flecks, a faint beauty mark below the right "
    "cheekbone. Hair: long wavy chestnut hair parted to the side, a few strands tucked "
    "behind the left ear. Outfit: sleeveless deep sapphire-blue dress, pink-quartz pendant "
    "necklace, matching earrings. Nails: almond-shaped, soft blush pink. Presence: warm, "
    "confident, magnetic, energetic Carioca vibes."
)

BACKGROUND_BLOCK = (
    "Background: A real open public square with mosaic paving, a stone fountain, benches, "
    "kiosks, and colorful trees (jacaranda and bougainvillea). People move in soft focus "
    "behind her; no readable signs or logos."
)

LIGHTING_BLOCK = (
    "Lighting: Golden-hour sunlight with warm flares and natural highlights on hair, "
    "skin, jewelry, and water."
)

STYLE_BLOCK = "Style: Hyper-realistic cinematic selfie, 9:16 vertical, gentle handheld movement."

AUDIO_BLOCK = (
    "Background sounds: Fountain water, soft city chatter, footsteps on stone, distant birds.\n"
    "Music: None"
)

TECH_BLOCK = (
    "Model: veo-3\n"
    "Length: 8 seconds\n"
    "Resolution: 1080p (9:16)\n"
    "Framerate: 24fps\n"
    "Negative prompt: No branding, no readable text, no fantasy effects, no facial change, "
    "no outfit inconsistency, no visual distortion."
)

VOICE_STYLE = "Voice: female, highly cheerful, authentic Carioca accent from Rio de Janeiro"

# ── Estrutura das 5 cenas ────────────────────────────────────────────────────
# Cada cena define os campos fixos (ação, tom, objetivo).
# O Gemini preenche apenas: dialogo e texto_tela.

ESTRUTURA_CENAS = [
    {
        "numero": 1,
        "nome": "A Revelação",
        "subject_suffix": "delivering an upbeat and energetic hook.",
        "action": (
            "Ana records in selfie mode while walking slowly past the fountain, "
            "bringing the phone slightly closer, smiling with explosive energetic "
            "Carioca vibes, looking directly into the lens."
        ),
        "tone": "enthusiastic tone",
        "objetivo": (
            "Hook inicial que prende a atenção — pergunta ou afirmação impactante "
            "sobre o signo/tema. Deve fazer o espectador se identificar imediatamente."
        ),
    },
    {
        "numero": 2,
        "nome": "O Desafio",
        "subject_suffix": "delivering an empathetic but direct message.",
        "action": (
            "Ana continues walking, tilting her head with a playful, understanding look, "
            "keeping the selfie angle steady while moving past the colorful trees."
        ),
        "tone": "energetic tone",
        "objetivo": (
            "Identifica o maior desafio ou dificuldade do signo/tema de forma empática. "
            "O espectador deve pensar: 'é exatamente isso que acontece comigo'."
        ),
    },
    {
        "numero": 3,
        "nome": "A Transformação",
        "subject_suffix": "delivering a powerful revelation.",
        "action": (
            "Ana stops briefly, her eyes lighting up with vibrant excitement. "
            "The golden sun illuminates her chestnut hair as she smiles widely, "
            "radiating confidence."
        ),
        "tone": "exciting tone",
        "objetivo": (
            "Revela o dom ou força principal do signo/tema de forma poderosa. "
            "Deve causar uma virada emocional positiva no espectador."
        ),
    },
    {
        "numero": 4,
        "nome": "O Conselho",
        "subject_suffix": "sharing an exciting secret.",
        "action": (
            "Ana leans in close to the camera as if sharing a super exciting secret, "
            "her sapphire-blue dress catching the warm light, while she resumes her slow walk."
        ),
        "tone": "magnetic tone",
        "objetivo": (
            "Dá o conselho prático e direto de como usar o dom para atrair sorte e "
            "prosperidade. Deve soar como uma dica exclusiva que só Ana revelaria."
        ),
    },
    {
        "numero": 5,
        "nome": "O Chamado (CTA)",
        "subject_suffix": "delivering an energetic call to action.",
        "action": (
            "Ana gives a huge, animated smile, gesturing excitedly downwards towards "
            "the comments area with a blush-pink manicured hand, maintaining her vibrant vibe."
        ),
        "tone": "motivating tone",
        "objetivo": (
            "CTA direto e enérgico pedindo para comentar e interagir. "
            "Deve ativar o engajamento e terminar com energia alta."
        ),
    },
]