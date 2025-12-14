"""LLM backend (Ollama) with a simple fallback.

Requires: `ollama` CLI + model `bielik-4b-v3.0` for best results.
"""
import subprocess
import shlex


def generate_story(prompt: str = None, model: str = "bielik-4b-v3.0", ollama_url: str | None = None) -> str:
    if prompt is None:
        prompt = 'Napisz brainrotową, absurdalną historyjkę na YouTube Shorts (max 80 słów), z twistem na końcu. Po polsku.'
    # If ollama_url provided, try HTTP endpoint (best-effort)
    if ollama_url and ollama_url.startswith('http'):
        import requests
        endpoints = [
            ollama_url.rstrip('/') + '/api/generate',
            ollama_url.rstrip('/') + '/api/predict',
            ollama_url.rstrip('/') + '/generate',
            ollama_url.rstrip('/') + '/predict',
        ]
        payloads = [
            {'model': model, 'prompt': prompt},
            {'prompt': prompt, 'model': model},
            {'input': prompt, 'model': model},
        ]
        for ep in endpoints:
            for payload in payloads:
                try:
                    r = requests.post(ep, json=payload, timeout=8)
                    if r.status_code != 200:
                        continue
                    try:
                        j = r.json()
                        # Try common fields
                        for key in ['text', 'output', 'result', 'generation', 'content']:
                            if key in j and isinstance(j[key], str):
                                return j[key].strip()
                        # OpenAI-like choices
                        if 'choices' in j and isinstance(j['choices'], list) and len(j['choices']) > 0:
                            c = j['choices'][0]
                            if isinstance(c, dict) and ('text' in c or 'message' in c):
                                return (c.get('text') or c.get('message') or '').strip()
                    except Exception:
                        # if response is plain text
                        if r.text and len(r.text.strip()) > 0:
                            return r.text.strip()
                except Exception:
                    continue

    # Try Ollama CLI
    try:
        cmd = ["ollama", "run", model, prompt]
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
        out = p.stdout.strip()
        if out:
            return out
    except FileNotFoundError:
        pass

    # Fallback sample (very simple)
    sample = (
        "Kot znalazł pilota do wszechświata. Każde naciśnięcie zmieniało jedną regułę rzeczywistości. "
        "Na końcu pilot sam wcisnął przycisk — i obudziłeś się czytając tę historyjkę?"
    )
    return sample


if __name__ == '__main__':
    print(generate_story())
