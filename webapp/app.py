from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import subprocess
import time
import os
from pathlib import Path
import base64
import requests
import sys

# Ensure project root is importable when running webapp directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _get_modules():
    try:
        from yt_brainrot import llm as llm_mod, tts as tts_mod, visual as visual_mod, sd_a1111 as sd_mod, editor as editor_mod
        return llm_mod, tts_mod, visual_mod, sd_mod, editor_mod
    except Exception as e:
        raise RuntimeError(f"Unable to import internal modules: {e}. Try running with PYTHONPATH=. or install package")

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)


def build_metadata(story: str):
    """Create simple title/description/tags from generated story."""
    if not story:
        return ('', '', [])
    title = story.strip().split('\n')[0]
    if len(title) > 80:
        title = title[:77] + '...'
    description = story.strip()
    tags = [t.strip('# ').lower() for t in ['brainrot', 'shorts', 'absurd']]
    return (title, description, tags)


def _generate_tts_bytes(text: str, piper_url: str | None = None, coqui_url: str | None = None, voice: str | None = None, speed: float | None = None):
    """Return tuple (bytes, meta_dict). Try remote synth first, fall back to local backends."""
    outdir = Path('outputs') / 'functions' / str(int(time.time()))
    outdir.mkdir(parents=True, exist_ok=True)

    remote_url = piper_url or coqui_url
    if remote_url:
        # try /synthesize then base URL
        candidates = [remote_url.rstrip('/') + '/synthesize', remote_url]
        for url in candidates:
            try:
                r = requests.post(url, json={'text': text, 'voice': voice, 'speed': speed}, timeout=30)
                if r.status_code == 200:
                    ct = r.headers.get('Content-Type', '')
                    if ct.startswith('audio/'):
                        return (r.content, {'backend': url, 'voice': voice, 'format': 'wav'})
                    try:
                        jd = r.json()
                        aud = jd.get('audio') or jd.get('wav') or jd.get('data')
                        if aud:
                            if isinstance(aud, str):
                                b = base64.b64decode(aud)
                            else:
                                b = aud
                            return (b, {'backend': url, 'voice': voice, 'format': 'wav'})
                    except Exception:
                        pass
            except Exception:
                continue

    # local fallback
    wav_path = outdir / 'out.wav'
    _, tts_mod, _, _, _ = _get_modules()
    meta = tts_mod.tts_to_wav(text, str(wav_path), voice=voice, speed=speed)
    with open(meta['path'], 'rb') as f:
        data = f.read()
    return (data, meta)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate', methods=['POST'])
def generate():
    data = request.json or {}
    count = int(data.get('count', 1))
    publish = bool(data.get('publish', False))

    timestamp = int(time.time())
    outdir = Path('outputs') / f'web_{timestamp}'
    outdir_str = str(outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    cmd = ['python', os.path.join(os.getcwd(), 'scripts', 'pipeline.py'), '--count', str(count), '--outdir', outdir_str]
    if publish:
        cmd.append('--publish')

    try:
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return jsonify({
            'success': p.returncode == 0,
            'stdout': p.stdout,
            'stderr': p.stderr,
            'outdir': outdir_str
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Supabase Functions-compatible endpoints under /functions/v1/<name>


@app.route('/functions/v1/generate-story', methods=['POST'])
def fn_generate_story():
    body = request.get_json() or {}
    prompt = body.get('prompt') or body.get('storyPrompt')
    ollama_url = body.get('ollamaUrl') or body.get('ollama_url')
    model = body.get('model') or body.get('ollamaModel') or 'bielik-4b-v3.0'
    try:
        # Lazy import modules
        llm_mod, _, _, _, _ = _get_modules()
        # If an Ollama URL is provided, pass it to the LLM layer for best-effort HTTP call
        story = llm_mod.generate_story(prompt, model=model, ollama_url=ollama_url)
        return jsonify({'story': story, 'model': model})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/functions/v1/generate-tts', methods=['POST'])
def fn_generate_tts():
    body = request.get_json() or {}
    text = body.get('text') or body.get('input') or ''
    voice = body.get('voice') or body.get('voiceName') or os.environ.get('TTS_VOICE', None)
    speed = body.get('speed') or body.get('piperSpeed') or None
    try:
        outdir = Path('outputs') / 'functions' / str(int(time.time()))
        outdir.mkdir(parents=True, exist_ok=True)

        # First try remote TTS if URL supplied
        remote_url = body.get('piperUrl') or body.get('coquiUrl')
        if remote_url:
            # Try POSTing to remote endpoint with common payload {text, voice, speed}
            try:
                r = requests.post(remote_url.rstrip('/') + '/synthesize', json={'text': text, 'voice': voice, 'speed': speed}, timeout=30)
                if r.status_code == 200:
                    # If response content-type is audio, use raw bytes
                    ct = r.headers.get('Content-Type', '')
                    if ct.startswith('audio/'):
                        wav_path = outdir / 'out.wav'
                        with open(wav_path, 'wb') as f:
                            f.write(r.content)
                        b = base64.b64encode(r.content).decode('utf-8')
                        return jsonify({'format': 'wav', 'voice': voice, 'backend': remote_url, 'audio': b})
                    # Otherwise expect JSON with base64 audio
                    try:
                        jd = r.json()
                        aud = jd.get('audio') or jd.get('wav') or jd.get('data')
                        if aud:
                            if isinstance(aud, str):
                                # assume base64
                                b = aud
                            else:
                                b = base64.b64encode(aud).decode('utf-8')
                            return jsonify({'format': 'wav', 'voice': voice, 'backend': remote_url, 'audio': b})
                    except Exception:
                        pass
                # if remote call failed, fall through to local
            except Exception:
                pass

        wav_path = outdir / 'out.wav'
        _, tts_mod, _, _, _ = _get_modules()
        meta = tts_mod.tts_to_wav(text, str(wav_path), voice=voice, speed=speed)
        with open(meta['path'], 'rb') as f:
            b = base64.b64encode(f.read()).decode('utf-8')
        return jsonify({'format': meta.get('format', 'wav'), 'voice': meta.get('voice'), 'backend': meta.get('backend'), 'audio': b})
    except Exception as e:
        return jsonify({'error': str(e), 'hint': 'Install Coqui TTS or Piper for better voices'}), 500


@app.route('/functions/v1/tts-voices', methods=['GET'])
def fn_tts_voices():
    try:
        _, tts_mod, _, _, _ = _get_modules()
        v = tts_mod.list_voices()
        # Flatten into a simple list of voice identifiers for the frontend
        flat = []
        if isinstance(v, dict):
            for backend, items in v.items():
                if isinstance(items, (list, tuple)):
                    for it in items:
                        flat.append(f"{backend}:{it}")
                else:
                    flat.append(f"{backend}:{items}")
        else:
            try:
                for it in v:
                    flat.append(str(it))
            except Exception:
                flat = [str(v)]
        return jsonify({'voices': flat})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/functions/v1/generate-image', methods=['POST'])
def fn_generate_image():
    body = request.get_json() or {}
    prompt = body.get('prompt') or ''
    try:
        outdir = Path('outputs') / 'functions' / str(int(time.time()))
        outdir.mkdir(parents=True, exist_ok=True)
        img_path = outdir / 'out.jpg'
        # Prefer A1111 if available
        host = body.get('sdUrl') or os.environ.get('A1111_HOST', 'http://127.0.0.1:7860')
        meta = None
        _, _, visual_mod, sd_mod, _ = _get_modules()
        if sd_mod.is_server_alive(host):
            meta = sd_mod.generate_image_a1111(prompt, str(img_path), host=host, width=720, height=1280)
            # meta is a dict with 'path' and optional 'seed' and 'prompt'
            if isinstance(meta, dict):
                img_path = Path(meta.get('path', str(img_path)))
        else:
            visual_mod.create_background_from_prompt(prompt, str(img_path), size=(720, 1280))
        with open(img_path, 'rb') as f:
            b = base64.b64encode(f.read()).decode('utf-8')
        response = {'image': b, 'prompt': prompt}
        if isinstance(meta, dict):
            response['seed'] = meta.get('seed')
            response['prompt'] = meta.get('prompt', prompt)
        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e), 'hint': 'Run A1111 WebUI or fallback will generate simple image'}), 500


@app.route('/functions/v1/pipeline-status', methods=['POST', 'GET'])
def fn_pipeline_status():
    # Check basic services: Ollama (ollama CLI or provided URL), A1111, ffmpeg
    body = request.get_json() or {}
    ollama_url = body.get('ollamaUrl') or body.get('ollama_url')
    piper_url = body.get('piperUrl') or body.get('piper_url')
    sd_url = body.get('sdUrl') or body.get('sd_url')

    services = []

    # Ollama: check HTTP URL if provided else CLI
    try:
        import shutil
        if ollama_url:
            try:
                r = requests.get(ollama_url.rstrip('/') + '/api/version', timeout=2)
                ok = r.status_code == 200
            except Exception:
                ok = False
            services.append({'name': 'Ollama', 'url': ollama_url, 'status': 'online' if ok else 'offline'})
        else:
            ollama_ok = shutil.which('ollama') is not None
            services.append({'name': 'Ollama', 'url': None, 'status': 'online' if ollama_ok else 'offline'})
    except Exception:
        services.append({'name': 'Ollama', 'url': None, 'status': 'unknown'})

    # A1111
    try:
        _, _, _, sd_mod, _ = _get_modules()
        host = sd_url or os.environ.get('A1111_HOST', 'http://127.0.0.1:7860')
        a1111_ok = sd_mod.is_server_alive(host)
        services.append({'name': 'A1111', 'url': host, 'status': 'online' if a1111_ok else 'offline'})
    except Exception:
        services.append({'name': 'A1111', 'url': None, 'status': 'unknown'})

    # FFmpeg
    try:
        import shutil
        ffmpeg_ok = shutil.which('ffmpeg') is not None
        services.append({'name': 'FFmpeg', 'url': None, 'status': 'online' if ffmpeg_ok else 'offline'})
    except Exception:
        services.append({'name': 'FFmpeg', 'url': None, 'status': 'unknown'})

    return jsonify({'services': services, 'allOnline': all(s['status'] == 'online' for s in services)})


@app.route('/functions/v1/list-outputs', methods=['GET'])
def fn_list_outputs():
    """Return a list of recent pipeline output folders with summary info."""
    base = Path('outputs') / 'functions'
    items = []
    if base.exists():
        for d in sorted(base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
            if d.is_dir():
                files = {p.name: str(p) for p in d.iterdir()}
                info = {
                    'id': d.name,
                    'path': str(d),
                    'files': list(files.keys()),
                    'mtime': int(d.stat().st_mtime)
                }
                items.append(info)
    return jsonify({'items': items})


@app.route('/functions/v1/get-file', methods=['GET'])
def fn_get_file():
    """Serve an output file by path (query param `path`)."""
    p = request.args.get('path')
    if not p:
        return jsonify({'error': 'path query param required'}), 400
    fp = Path(p)
    if not fp.exists() or not fp.is_file():
        return jsonify({'error': 'file not found'}), 404
    from flask import send_file
    return send_file(str(fp), as_attachment=False)


@app.route('/functions/v1/run-pipeline', methods=['POST'])
def fn_run_pipeline():
    body = request.get_json() or {}
    # Run modular pipeline: story -> tts -> image -> video
    pipeline_id = str(int(time.time()))
    started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    result = {
        'pipelineId': pipeline_id,
        'startedAt': started,
        'overallStatus': 'pending',
        'steps': {}
    }
    try:
        # Flags from frontend
        generate_image = body.get('generateImage', True)
        generate_tts = body.get('generateTTS', True)
        generate_story = body.get('generateStory', True)
        publish_flag = bool(body.get('publish', False))

        prompt = body.get('storyPrompt') or 'Napisz brainrotową, absurdalną historyjkę na YouTube Shorts (max 80 słów), z twistem na końcu.'

        outdir = Path('outputs') / 'functions' / pipeline_id
        outdir.mkdir(parents=True, exist_ok=True)

        # Story
        ollama_url = body.get('ollamaUrl') or body.get('ollama_url') or None
        llm_mod, tts_mod, visual_mod, sd_mod, editor_mod = _get_modules()
        if generate_story:
            story = llm_mod.generate_story(prompt, model=body.get('ollamaModel') or None or 'bielik-4b-v3.0', ollama_url=ollama_url)
            result['steps']['story'] = {'status': 'completed', 'data': {'story': story}}
        else:
            # Use provided story if present
            story = body.get('story') or ''
            result['steps']['story'] = {'status': 'skipped', 'note': 'Skipped story generation'}

        # TTS
        wav_path = outdir / 'speech.wav'
        if generate_tts and story:
            try:
                # Directly call TTS module (supports remote HTTP TTS via http_url)
                http_url = body.get('piperUrl') or body.get('coquiUrl') or None
                meta = tts_mod.tts_to_wav(story, str(wav_path), voice=body.get('voice'), speed=body.get('speed') or body.get('piperSpeed'), http_url=http_url)
                with open(meta['path'], 'rb') as f:
                    audio_b64 = base64.b64encode(f.read()).decode('utf-8')
                result['steps']['tts'] = {'status': 'completed', 'data': {'format': meta.get('format', 'wav'), 'voice': meta.get('voice'), 'backend': meta.get('backend'), 'hasAudio': True}}
                result['audioBase64'] = audio_b64
            except Exception as e:
                result['steps']['tts'] = {'status': 'failed', 'error': str(e)}
        else:
            result['steps']['tts'] = {'status': 'skipped', 'note': 'Skipped TTS generation'}

        # Image
        img_path = outdir / 'bg.jpg'
        img_b64 = None
        if generate_image:
            try:
                host = body.get('sdUrl') or os.environ.get('A1111_HOST', 'http://127.0.0.1:7860')
                meta = None
                if sd_mod.is_server_alive(host):
                    meta = sd_mod.generate_image_a1111(story, str(img_path), host=host, width=720, height=1280)
                    if isinstance(meta, dict):
                        img_path = Path(meta.get('path', str(img_path)))
                else:
                    visual_mod.create_background_from_prompt(story, str(img_path), size=(720, 1280))
                with open(img_path, 'rb') as f:
                    img_b64 = base64.b64encode(f.read()).decode('utf-8')
                img_meta = {'hasImage': True}
                if isinstance(meta, dict):
                    img_meta['seed'] = meta.get('seed')
                    img_meta['prompt'] = meta.get('prompt')
                result['steps']['image'] = {'status': 'completed', 'data': img_meta}
                result['imageBase64'] = img_b64
            except Exception as e:
                result['steps']['image'] = {'status': 'failed', 'error': str(e)}
        else:
            result['steps']['image'] = {'status': 'skipped', 'note': 'Skipped image generation'}

        # Video: create small then upscale if we have audio and image
        if img_b64 and 'audioBase64' in result:
            try:
                small_video = outdir / 'short_small.mp4'
                editor_mod.create_short_from_image(str(img_path), str(wav_path), str(small_video), width=720, height=1280)
                final_video = outdir / 'short.mp4'
                editor_mod.upscale_video_to_1080x1920(str(small_video), str(final_video))
                result['steps']['video'] = {'status': 'completed', 'note': str(final_video)}
            except Exception as e:
                result['steps']['video'] = {'status': 'failed', 'error': str(e)}
        else:
            result['steps']['video'] = {'status': 'skipped', 'note': 'Not enough assets to build video'}

        # Publish (skeleton)
        if publish_flag and result['steps'].get('video', {}).get('status') == 'completed':
            try:
                from yt_brainrot import publisher as pub
                title, description, tags = build_metadata(story) if 'story' in locals() else ('', '', [])
                res = pub.publish_to_postiz(str(final_video), title, description, tags)
                result['steps']['publish'] = {'status': 'completed', 'note': 'Published via Postiz', 'response': res}
            except Exception as e:
                result['steps']['publish'] = {'status': 'failed', 'error': str(e)}
        else:
            result['steps']['publish'] = {'status': 'skipped', 'note': 'Publish not requested or no video'}
        result['overallStatus'] = 'completed'
        result['completedAt'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        return jsonify(result)
    except Exception as e:
        result['overallStatus'] = 'failed'
        result['error'] = str(e)
        return jsonify(result), 500


if __name__ == '__main__':
    port = int(os.environ.get('WEBAPP_PORT', os.environ.get('PORT', 5000)))
    debug = os.environ.get('FLASK_DEBUG', 'True').lower() in ('1', 'true', 'yes')
    app.run(host='0.0.0.0', port=port, debug=debug)
