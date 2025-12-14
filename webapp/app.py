from flask import Flask, render_template, request, jsonify
import subprocess
import time
import os
from pathlib import Path

app = Flask(__name__, static_folder='static', template_folder='templates')


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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
