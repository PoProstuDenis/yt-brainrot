"""Generowanie obrazu tła. Fallback: generuj prosty obraz 1080x1920 z tekstem.
Opcjonalnie: można podpiąć Stable Diffusion (diffusers) jeśli dostępne.
"""
from PIL import Image, ImageDraw, ImageFont
import random
from pathlib import Path
import os
from . import sd_a1111
import subprocess


def create_background_from_prompt(prompt: str, out_path: str, size=(1080, 1920)) -> str:
    out_path = str(out_path)
    # Prefer A1111 if available — generate at 720x1280 to save VRAM, then upscale later
    try:
        host = os.environ.get('A1111_HOST', 'http://127.0.0.1:7860')
        if sd_a1111.is_server_alive(host):
            small_w, small_h = 720, 1280
            tmp = str(Path(out_path).with_suffix('.a1111.tmp.jpg'))
            sd_a1111.generate_image_a1111(prompt, tmp, host=host, width=small_w, height=small_h)
            # Move tmp to out_path (we keep small size; upscaling handled by editor)
            Path(out_path).parent.mkdir(parents=True, exist_ok=True)
            os.replace(tmp, out_path)
            return out_path
    except Exception:
        pass

    # Fallback: create simple gradient + text at requested size (default 1080x1920)
    try:
        img = Image.new('RGB', size, color='black')
        draw = ImageDraw.Draw(img)
        # gradient
        for y in range(size[1]):
            r = int(30 + (y / size[1]) * 200)
            g = int(10 + (y / size[1]) * 120)
            b = int(40 + (y / size[1]) * 160)
            draw.line([(0, y), (size[0], y)], fill=(r, g, b))

        # draw noisy circles
        for _ in range(30):
            x = random.randint(0, size[0])
            y = random.randint(0, size[1])
            r = random.randint(20, 200)
            color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
            draw.ellipse((x - r, y - r, x + r, y + r), outline=color, width=2)

        # overlay prompt text
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 42)
        except Exception:
            font = ImageFont.load_default()

        lines = _wrap_text(prompt, font, size[0] - 80)
        y0 = 120
        for line in lines:
            # measure text size (font API may vary across Pillow versions)
            try:
                bbox = font.getbbox(line)
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            except Exception:
                try:
                    w, h = font.getsize(line)
                except Exception:
                    # fallback guess
                    w, h = (len(line) * 10, 20)
            draw.text(((size[0] - w) / 2, y0), line, font=font, fill=(255, 255, 255))
            y0 += h + 8

        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, quality=85)
        return out_path
    except Exception as e:
        raise


def _wrap_text(text, font, max_width):
    words = text.split()
    lines = []
    cur = ''
    for w in words:
        test = (cur + ' ' + w).strip()
        # measure text width safely
        try:
            bbox = font.getbbox(test)
            test_w = bbox[2] - bbox[0]
        except Exception:
            try:
                test_w = font.getsize(test)[0]
            except Exception:
                test_w = len(test) * 10
        if test_w <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


if __name__ == '__main__':
    create_background_from_prompt('surreal meme style, absurd brainrot aesthetic, low detail, vertical 9:16', 'out_bg.jpg')
