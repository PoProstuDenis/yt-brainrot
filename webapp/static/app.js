const runBtn = document.getElementById('run');
const log = document.getElementById('log');
runBtn.addEventListener('click', async () => {
  const count = document.getElementById('count').value;
  const publish = document.getElementById('publish').checked;
  log.textContent = 'Rozpoczynam generowanie...\n';
  runBtn.disabled = true;
  try {
    const res = await fetch('/generate', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({count: Number(count), publish})
    });
    const data = await res.json();
    if (data.success) {
      log.textContent += data.stdout + '\n';
      if (data.stderr) log.textContent += '\nErrors:\n' + data.stderr;
      log.textContent += '\nWyjscie zapisane w: ' + data.outdir;
    } else {
      log.textContent += 'Błąd:\n' + (data.stderr || data.error || 'nieznany');
    }
  } catch (e) {
    log.textContent += 'Wyjątek: ' + e;
  }
  runBtn.disabled = false;
});
