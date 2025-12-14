"""LLM backend (Ollama) with a simple fallback.

Requires: `ollama` CLI + model `bielik-4b-v3.0` for best results.
"""
import subprocess
import shlex


def generate_story(prompt: str = None, model: str = "bielik-4b-v3.0") -> str:
    if prompt is None:
        prompt = 'Napisz brainrotową, absurdalną historyjkę na YouTube Shorts (max 80 słów), z twistem na końcu. Po polsku.'

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
