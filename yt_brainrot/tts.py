
"""TTS backends: attempt Coqui TTS, Piper CLI, then pyttsx3/espeak fallback.
Provides `tts_to_wav` which returns metadata dict: {'path', 'voice', 'backend', 'format'}.
Also: `list_voices()` returns detected voices per backend (best-effort).
"""
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
import shutil


def _choose_piper_cmd(out_path: str, text: str, voice: Optional[str], speed: Optional[float]) -> list:
    cmd = ["piper", "--output", out_path, "--text", text]
    if voice:
        cmd += ["--voice", voice]
    if speed is not None:
        cmd += ["--speed", str(speed)]
    return cmd


def _try_http_tts(url: str, text: str, out_path: str, voice: Optional[str], speed: Optional[float]) -> bool:
    """Attempt to call a remote TTS HTTP endpoint using a few common paths and payloads.

    Accepts:
      - application/json responses with {'audio': '<base64>'} or {'wav': '<base64>'}
      - direct audio response with content-type audio/*
    Returns True on success and writes to out_path.
    """
    import requests
    endpoints = [
        url,
        url.rstrip('/') + '/synthesize',
        url.rstrip('/') + '/api/synthesize',
        url.rstrip('/') + '/api/tts',
        url.rstrip('/') + '/generate',
        url.rstrip('/') + '/api/generate',
        url.rstrip('/') + '/tts'
    ]
    headers = {'Accept': '*/*'}
    payload = {'text': text}
    if voice:
        payload['voice'] = voice
    if speed is not None:
        payload['speed'] = speed

    for ep in endpoints:
        try:
            r = requests.post(ep, json=payload, headers=headers, timeout=20)
            if r.status_code != 200:
                # try form-encoded
                r = requests.post(ep, data=payload, headers=headers, timeout=20)
            if r.status_code != 200:
                continue

            ctype = r.headers.get('Content-Type', '')
            if ctype.startswith('audio/'):
                with open(out_path, 'wb') as f:
                    f.write(r.content)
                return True

            # try json
            try:
                j = r.json()
                for key in ['audio', 'wav', 'file']:
                    if key in j and isinstance(j[key], str):
                        import base64
                        with open(out_path, 'wb') as f:
                            f.write(base64.b64decode(j[key]))
                        return True
            except Exception:
                pass
        except Exception:
            continue
    return False


def tts_to_wav(text: str, out_path: str, voice: Optional[str] = None, speed: Optional[float] = None, rate: Optional[int] = None, http_url: Optional[str] = None) -> Dict[str, Any]:
    """Generate WAV from text and return metadata dict.

    Returns: {'path': str, 'voice': str|null, 'backend': str, 'format': 'wav'}
    """
    out_path = str(out_path)

    # Try Coqui TTS first (if installed)
    try:
        from TTS.api import TTS
        tts = TTS()
        # Best-effort: if voice is provided, pass as 'speaker' kwarg
        kwargs = {}
        if voice:
            kwargs['speaker'] = voice
        try:
            tts.tts_to_file(text=text, file_path=out_path, **kwargs)
        except TypeError:
            # model may not accept speaker arg
            tts.tts_to_file(text=text, file_path=out_path)
        return {'path': out_path, 'voice': voice or 'coqui_default', 'backend': 'coqui', 'format': 'wav'}
    except Exception:
        pass

    # If http_url provided, attempt remote HTTP TTS first (Coqui/Piper servers)
    if http_url:
        try:
            ok = _try_http_tts(http_url, text, out_path, voice, speed)
            if ok:
                return {'path': out_path, 'voice': voice, 'backend': 'http', 'format': 'wav'}
        except Exception:
            pass

    # Try Piper CLI
    try:
        if shutil.which('piper'):
            cmd = _choose_piper_cmd(out_path, text, voice, speed)
            subprocess.run(cmd, check=True)
            if Path(out_path).exists():
                return {'path': out_path, 'voice': voice, 'backend': 'piper', 'format': 'wav'}
    except Exception:
        pass

    # Fallback: pyttsx3 (offline)
    try:
        import pyttsx3

        engine = pyttsx3.init()
        # rate: prefer explicit rate param; otherwise use speed multiplier if provided
        if rate:
            engine.setProperty('rate', rate)
        elif speed is not None:
            # pyttsx3 rate is words per minute; choose a baseline 200
            engine.setProperty('rate', int(200 * float(speed)))

        used_voice = None
        if voice:
            voices = engine.getProperty('voices')
            # try to match by id or name substring
            for v in voices:
                if voice in v.id or voice in getattr(v, 'name', ''):
                    engine.setProperty('voice', v.id)
                    used_voice = getattr(v, 'name', v.id)
                    break

        tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        tmp_path = tmp.name
        tmp.close()
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        os.replace(tmp_path, out_path)
        return {'path': out_path, 'voice': used_voice or voice or 'pyttsx3_default', 'backend': 'pyttsx3', 'format': 'wav'}
    except Exception:
        pass

    # Fallback: espeak / espeak-ng CLI
    try:
        cmd = None
        espeak_bin = 'espeak'
        if shutil.which('espeak') is None and shutil.which('espeak-ng') is not None:
            espeak_bin = 'espeak-ng'
        # Build command: espeak -w out.wav -s <speed> -v <voice> "text"
        cmd = [espeak_bin, '-w', out_path]
        if speed is not None:
            # convert relative speed to wpm (espeak default ~170)
            try:
                wpm = int(170 * float(speed))
            except Exception:
                wpm = 170
            cmd += ['-s', str(max(80, min(450, wpm)))]
        if voice:
            cmd += ['-v', voice]
        cmd += [text]
        subprocess.run(cmd, check=True)
        if Path(out_path).exists():
            return {'path': out_path, 'voice': voice or espeak_bin, 'backend': espeak_bin, 'format': 'wav'}
    except Exception:
        pass

    raise RuntimeError('No available TTS backend (install Coqui TTS, Piper CLI or pyttsx3).')


def list_voices() -> dict:
    """Return available voices per backend (best-effort)."""
    res = {}
    # pyttsx3
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        res['pyttsx3'] = [getattr(v, 'name', v.id) for v in voices]
    except Exception:
        res['pyttsx3'] = []

    # piper
    try:
        if shutil.which('piper'):
            out = subprocess.check_output(['piper', '--list-voices'], text=True)
            # try to parse lines
            lines = [l.strip() for l in out.splitlines() if l.strip()]
            res['piper'] = lines
        else:
            res['piper'] = []
    except Exception:
        res['piper'] = []

    # espeak
    try:
        espeak_bin = 'espeak'
        if shutil.which('espeak') is None and shutil.which('espeak-ng') is not None:
            espeak_bin = 'espeak-ng'
        out = subprocess.check_output([espeak_bin, '--voices'], text=True)
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        res['espeak'] = lines
    except Exception:
        res['espeak'] = []

    # coqui: not standardized — return empty or models if available
    try:
        from TTS.api import TTS
        models = TTS.list_models() if hasattr(TTS, 'list_models') else []
        res['coqui_models'] = models
    except Exception:
        res['coqui_models'] = []

    return res


if __name__ == '__main__':
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else 'out.wav'
    print(tts_to_wav('Przykładowa historyjka brainrot.', out))
