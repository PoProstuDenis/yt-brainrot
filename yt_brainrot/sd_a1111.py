"""Integracja z Automatic1111 WebUI (A1111) przez lokalne API.

Funkcje:
- `generate_image_a1111(prompt, out_path, host)` — wysyła żądanie do /sdapi/v1/txt2img i zapisuje obraz.

Uwaga: wymagane uruchomione A1111 na hoście (domyślnie http://127.0.0.1:7860).
Dla niskiego VRAM (RTX4050 6GB) rekomendacje w README.
"""
import base64
import io
import requests
from pathlib import Path
from typing import Optional


def is_server_alive(host: str = 'http://127.0.0.1:7860') -> bool:
    try:
        r = requests.get(f'{host}/sdapi/v1/version', timeout=2)
        return r.status_code == 200
    except Exception:
        return False


def generate_image_a1111(prompt: str, out_path: str, host: str = 'http://127.0.0.1:7860',
                         width: int = 1080, height: int = 1920, steps: int = 20,
                         sampler: str = 'Euler a', cfg_scale: float = 7.0, seed: Optional[int] = -1) -> str:
    """Wywołaj A1111 txt2img i zapisz wynik jako plik JPG/PNG.

    Jeśli A1111 nie jest dostępny, wyjątek zostanie rzucony.
    Dla RTX4050 warto używać mniejszych rozdzielczości lub opcji --medvram na WebUI.
    """
    if not is_server_alive(host):
        raise RuntimeError(f'Automatic1111 server not reachable at {host}')

    payload = {
        'prompt': prompt,
        'negative_prompt': 'lowres, bad anatomy, text, watermark',
        'width': width,
        'height': height,
        'sampler_index': sampler,
        'steps': steps,
        'cfg_scale': cfg_scale,
        'seed': seed,
        'restore_faces': False,
        'override_settings': {},
    }

    r = requests.post(f'{host}/sdapi/v1/txt2img', json=payload, timeout=120)
    r.raise_for_status()
    j = r.json()
    images = j.get('images', [])
    if not images:
        raise RuntimeError('No image returned from A1111')

    img_b64 = images[0]
    img_bytes = base64.b64decode(img_b64)
    out_p = Path(out_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    with open(out_p, 'wb') as f:
        f.write(img_bytes)

    # Try to extract seed and prompt from response info if present
    seed = None
    resp_prompt = prompt
    try:
        info = j.get('info')
        if info:
            import json as _json
            try:
                info_j = _json.loads(info)
                seed = info_j.get('seed') or info_j.get('all_seeds')
                # some versions put the prompt under 'prompt'
                resp_prompt = info_j.get('prompt', prompt)
            except Exception:
                # info may be a string that contains 'seed: ' etc.; best-effort parse
                if isinstance(info, str) and 'seed' in info:
                    # attempt simple parse
                    try:
                        parts = [p.strip() for p in info.split(',')]
                        for p in parts:
                            if p.startswith('seed'):
                                seed = int(p.split(':')[-1].strip())
                                break
                    except Exception:
                        pass
    except Exception:
        pass

    return {'path': str(out_p), 'seed': seed, 'prompt': resp_prompt}


if __name__ == '__main__':
    example_prompt = 'surreal meme style, absurd brainrot aesthetic, low detail, vertical 9:16'
    try:
        p = generate_image_a1111(example_prompt, '/tmp/a1111_out.jpg')
        print('Saved', p)
    except Exception as e:
        print('A1111 generate failed:', e)
