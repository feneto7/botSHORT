import os
import re
import uuid
import time
import asyncio
import shutil
import traceback
import urllib.parse
import requests
from flask import Flask, render_template, request, jsonify
import edge_tts
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types

app = Flask(__name__)

# ─── Configurações ───────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR     = os.path.join(BASE_DIR, 'temp')
OUTPUT_DIR   = os.path.join(BASE_DIR, 'static', 'output')
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Gemini – usado apenas para GERAR O ROTEIRO (texto), não para imagens
from dotenv import load_dotenv
load_dotenv()
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', 'API TOKEN AQUI')
client = genai.Client(api_key=GEMINI_API_KEY)

TEXT_MODEL  = "gemini-2.5-flash"

VIDEO_W = 720
VIDEO_H = 1280
MAX_SCENES = 15

VOICES = {
    "pt-BR-AntonioNeural":  "Masculino (Antonio)",
    "pt-BR-FranciscaNeural":"Feminino (Francisca)",
    "pt-BR-ThalitaNeural":  "Feminino (Thalita)",
}


# ─── Funções auxiliares ──────────────────────────────────────────

def split_script_into_scenes(script: str) -> list[str]:
    """Divide o roteiro em cenas (uma cena por frase)."""
    sentences = re.split(r'(?<=[.!?])\s+', script.strip())
    scenes = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 3]
    return scenes[:MAX_SCENES]


async def generate_tts(text: str, output_path: str, voice: str):
    """Gera áudio TTS com edge-tts (gratuito, sem chave de API)."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


def generate_image(prompt: str, output_path: str) -> bool:
    """
    Gera imagem estilo bonecos palitos usando Pollinations.ai (GRATUITO, sem API key).
    """
    full_prompt = (
        f"high quality digital art, vibrant colors, beautifully detailed illustration, "
        f"colorful cartoon or comic style, well drawn, masterpiece, no text, no words, no letters, "
        f"vertical portrait composition, scene: {prompt}"
    )
    try:
        encoded = urllib.parse.quote(full_prompt)
        seed = int(time.time() * 1000) % 1000000  # evita cache/repetição de imagem
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width=720&height=1280&nologo=true&seed={seed}"
        )
        resp = requests.get(url, timeout=90)
        if resp.status_code == 200 and len(resp.content) > 1000:
            with open(output_path, 'wb') as f:
                f.write(resp.content)
            return True
        print(f"[ERRO IMG] status code: {resp.status_code}")
        return False
    except Exception as e:
        print(f"[ERRO IMG] {e}")
        return False


def create_fallback_image(output_path: str):
    """Cria imagem de fallback simples se a geração falhar."""
    img = Image.new('RGB', (VIDEO_W, VIDEO_H), color=(35, 35, 55))
    draw = ImageDraw.Draw(img)
    draw.text((VIDEO_W // 2, VIDEO_H // 2), "🎬",
              fill='white', anchor='mm')
    img.save(output_path)


def load_font(size: int = 34):
    """Tenta carregar uma fonte TrueType em vários SOs."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "arialbd.ttf",
    ]
    for fp in candidates:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()


def process_scene_image(raw_path: str, subtitle: str, output_path: str):
    """Redimensiona a imagem para 720×1280 e adiciona legenda queimada."""
    img = Image.open(raw_path).convert('RGB')

    # Crop tipo "cover" para 9:16
    img_ratio = img.width / img.height
    target_ratio = VIDEO_W / VIDEO_H
    if img_ratio > target_ratio:
        new_w = int(img.height * target_ratio)
        left = (img.width - new_w) // 2
        img = img.crop((left, 0, left + new_w, img.height))
    else:
        new_h = int(img.width / target_ratio)
        top = (img.height - new_h) // 2
        img = img.crop((0, top, img.width, top + new_h))
    img = img.resize((VIDEO_W, VIDEO_H), Image.LANCZOS)

    # Overlay de legenda
    overlay = Image.new('RGBA', (VIDEO_W, VIDEO_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = load_font(34)

    # Quebra de linha automática
    words = subtitle.split()
    lines, current = [], []
    max_w = VIDEO_W - 80
    for w in words:
        test = ' '.join(current + [w])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_w:
            current.append(w)
        else:
            if current:
                lines.append(' '.join(current))
            current = [w]
    if current:
        lines.append(' '.join(current))

    # Caixa semitransparente + texto
    line_h = 42
    total_h = len(lines) * line_h
    box_y = VIDEO_H - total_h - 90

    draw.rectangle(
        [30, box_y - 15, VIDEO_W - 30, box_y + total_h + 10],
        fill=(0, 0, 0, 175)
    )

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = (VIDEO_W - tw) // 2
        y = box_y + i * line_h
        # contorno
        for dx, dy in [(-2,0),(2,0),(0,-2),(0,2),(-2,-2),(2,2),(-2,2),(2,-2)]:
            draw.text((x+dx, y+dy), line, fill=(0,0,0,255), font=font)
        draw.text((x, y), line, fill=(255,255,255,255), font=font)

    result = Image.alpha_composite(img.convert('RGBA'), overlay)
    result.convert('RGB').save(output_path, 'JPEG', quality=95)


def generate_script_from_topic(topic: str) -> str:
    """Gera roteiro a partir de um tópico usando Gemini texto."""
    prompt = (
        f"Crie um roteiro curto e divertido para um vídeo YouTube Shorts sobre: {topic}. "
        "O roteiro deve ter entre 5 e 10 frases, cada frase descrevendo uma cena diferente. "
        "Use linguagem simples, direta e envolvente. "
        "Retorne apenas o roteiro em texto corrido, sem numeração nem marcadores."
    )
    response = client.models.generate_content(model=TEXT_MODEL, contents=[prompt])
    return response.text.strip()


# ─── Rotas Flask ─────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html', voices=VOICES)


@app.route('/generate_script', methods=['POST'])
def gen_script():
    data = request.json
    topic = data.get('topic', '').strip()
    if not topic:
        return jsonify({'error': 'Tópico vazio'}), 400
    try:
        script = generate_script_from_topic(topic)
        return jsonify({'script': script})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/generate', methods=['POST'])
def generate_video():
    data = request.json
    script = data.get('script', '').strip()
    voice  = data.get('voice', 'pt-BR-AntonioNeural')

    if not script:
        return jsonify({'error': 'Roteiro vazio'}), 400

    session_id = str(uuid.uuid4())[:8]
    temp_dir = os.path.join(TEMP_DIR, session_id)
    os.makedirs(temp_dir, exist_ok=True)

    try:
        scenes = split_script_into_scenes(script)
        if not scenes:
            return jsonify({'error': 'Não foi possível extrair cenas do roteiro'}), 400

        clips = []

        for i, scene in enumerate(scenes):
            print(f"  Cena {i+1}/{len(scenes)}: {scene[:60]}...")

            # 1) TTS
            audio_path = os.path.join(temp_dir, f"audio_{i}.mp3")
            asyncio.run(generate_tts(scene, audio_path, voice))
            audio_clip = AudioFileClip(audio_path)
            duration = audio_clip.duration + 0.4   # pequeno buffer

            # 2) Imagem (Pollinations.ai)
            raw_img_path = os.path.join(temp_dir, f"raw_{i}.png")
            if not generate_image(scene, raw_img_path):
                create_fallback_image(raw_img_path)

            # 3) Processa imagem + legenda
            final_img_path = os.path.join(temp_dir, f"scene_{i}.jpg")
            process_scene_image(raw_img_path, scene, final_img_path)

            # 4) Cria clip de vídeo
            clip = ImageClip(final_img_path).with_duration(duration)
            clip = clip.with_audio(audio_clip)
            clips.append(clip)

        # 5) Concatena tudo
        print("Montando vídeo final...")
        final = concatenate_videoclips(clips)

        output_name = f"video_{session_id}.mp4"
        output_path = os.path.join(OUTPUT_DIR, output_name)
        final.write_videofile(
            output_path,
            fps=24,
            codec='libx264',
            audio_codec='aac',
            preset='medium',
            threads=4,
            logger=None
        )

        for c in clips:
            c.close()
        final.close()

        shutil.rmtree(temp_dir, ignore_errors=True)

        return jsonify({
            'success': True,
            'video_url': f'/static/output/{output_name}',
            'scenes_count': len(scenes)
        })

    except Exception as e:
        shutil.rmtree(temp_dir, ignore_errors=True)
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000, threaded=True)