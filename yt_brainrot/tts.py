"""TTS backends: attempt Coqui TTS, Piper CLI, then pyttsx3 fallback.
Produces WAV file.
"""
import os
import subprocess
import tempfile
from pathlib import Path


def tts_to_wav(text: str, out_path: str, rate: int = 210) -> str:
    out_path = str(out_path)
    # Try Coqui TTS
    try:
        from TTS.api import TTS
        # Use default model if available; this requires user to install model weights
        tts = TTS()
        tts.tts_to_file(text=text, file_path=out_path)
        return out_path
    except Exception:
        pass

    # Try Piper CLI
    try:
        # Example: piper --model some-model --voice some-voice --output out.wav --text '...'
        # User must adapt model/voice if needed; here we attempt a generic call
        cmd = ["piper", "--output", out_path, "--text", text]
        subprocess.run(cmd, check=True)
        if Path(out_path).exists():
            return out_path
    except Exception:
        pass

    # Fallback: pyttsx3 (robotyczny, działa offline)
    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty('rate', rate)
        # Save to temporary file then move (some drivers need file-like)
        tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        tmp_path = tmp.name
        tmp.close()
        engine.save_to_file(text, tmp_path)
        engine.runAndWait()
        os.replace(tmp_path, out_path)
        return out_path
    except Exception:
        pass

    # Fallback: espeak / espeak-ng if available (very small, offline)
    try:
        # espeak-ng -w out.wav "text"
        cmd = ["espeak-ng", "-w", out_path, text]
        subprocess.run(cmd, check=True)
        if Path(out_path).exists():
            return out_path
    except Exception:
        try:
            cmd = ["espeak", "-w", out_path, text]
            subprocess.run(cmd, check=True)
            if Path(out_path).exists():
                return out_path
        except Exception:
            pass

    # Fallback: espeak/espeak-ng CLI (offline, lightweight)
    try:
        # espeak: -w <file> -s <speed> -v <voice/lang>
        speed = max(80, min(300, rate))
        cmd = ["espeak", "-w", out_path, "-s", str(speed), "-v", "pl"]
        # some systems have espeak-ng installed as `espeak-ng`
        try:
            import shutil
            if shutil.which('espeak') is None and shutil.which('espeak-ng') is not None:
                cmd[0] = 'espeak-ng'
        except Exception:
            pass
        subprocess.run(cmd, check=True)
        return out_path
    except Exception:
        pass

    raise RuntimeError('No available TTS backend (install Coqui TTS, Piper CLI or pyttsx3).')


if __name__ == '__main__':
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else 'out.wav'
    tts_to_wav('Przykładowa historyjka brainrot.', out)
