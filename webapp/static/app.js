const API = {
  status: '/functions/v1/pipeline-status',
  voices: '/functions/v1/tts-voices',
  run: '/functions/v1/run-pipeline',
  list: '/functions/v1/list-outputs',
  getFile: '/functions/v1/get-file'
};

let queue = [];
let running = false;

function el(id){return document.getElementById(id)}

async function refreshStatus(){
  try{
    const r = await fetch(API.status);
    const j = await r.json();
    const sv = j.services || [];
    sv.forEach(s => {
      const id = s.name.toLowerCase();
      const elId = id === 'a1111' ? 'svc-sd' : id === 'piper' ? 'svc-piper' : id === 'ollama' ? 'svc-ollama' : null;
      if(elId){
        const node = el(elId);
        node.textContent = s.status;
        node.className = 'badge ' + (s.status === 'online' ? 'online' : s.status === 'offline' ? 'offline' : 'unknown');
      }
    });
  }catch(e){console.warn('status failed', e)}
}

async function loadVoices(){
  try{
    const r = await fetch(API.voices);
    const j = await r.json();
    const voices = j.voices || [];
    const sel = el('voice-select');
    sel.innerHTML = '';
    voices.forEach(v => {
      const o = document.createElement('option'); o.value = v; o.textContent = v; sel.appendChild(o);
    });
    if(!voices.length){
      const o = document.createElement('option'); o.value = 'pl_PL-gosia-medium'; o.textContent = 'pl_PL-gosia-medium (fallback)'; sel.appendChild(o);
    }
  }catch(e){console.warn('voices failed', e)}
}

function saveConfig(){
  const cfg = {
    ollamaUrl: el('cfg-ollama').value || null,
    piperUrl: el('cfg-piper').value || null,
    sdUrl: el('cfg-sd').value || null
  };
  localStorage.setItem('yt_brainrot_cfg', JSON.stringify(cfg));
  el('cfg-saved').textContent = 'Aktualne ustawienia zapisane w localStorage.';
}

function loadConfig(){
  const raw = localStorage.getItem('yt_brainrot_cfg');
  if(raw){
    try{const cfg = JSON.parse(raw); el('cfg-ollama').value = cfg.ollamaUrl || ''; el('cfg-piper').value = cfg.piperUrl || ''; el('cfg-sd').value = cfg.sdUrl || '';}catch(e){}
  }
}

function enqueue(n){
  for(let i=0;i<n;i++) queue.push({id: Date.now()+'-'+i, status:'queued'});
  renderQueue();
  if(!running) runQueue();
}

function renderQueue(){
  const ul = el('queue'); ul.innerHTML='';
  queue.forEach((it, idx)=>{
    const li = document.createElement('li'); li.id = 'q-'+it.id; li.textContent = `${idx+1}. ${it.status}`; ul.appendChild(li);
  });
}

async function runQueue(){
  running = true;
  while(queue.length){
    const item = queue.shift();
    item.status = 'running'; renderQueue();
    try{
      const res = await runPipelineOnce();
      item.status = 'done';
      updateLastResult();
    }catch(e){
      item.status = 'failed'; console.error('pipeline run failed', e);
    }
    renderQueue();
  }
  running = false;
}

async function runPipelineOnce(){
  const body = {
    generateStory: !!el('step-story').checked,
    generateTTS: !!el('step-tts').checked,
    generateImage: !!el('step-image').checked,
    publish: false,
    storyPrompt: null,
    piperUrl: el('cfg-piper').value || null,
    coquiUrl: null,
    ollamaUrl: el('cfg-ollama').value || null,
    sdUrl: el('cfg-sd').value || null,
    voice: el('voice-select').value || null,
    speed: parseFloat(el('voice-speed').value) || 1.0
  };
  const r = await fetch(API.run, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const j = await r.json();
  if(r.status !== 200) throw new Error(JSON.stringify(j));
  return j;
}

async function updateLastResult(){
  // query list-outputs and take latest
  try{
    const r = await fetch(API.list);
    const j = await r.json();
    const items = j.items || [];
    if(!items.length){ el('last-result').innerHTML = 'Brak wyników'; return; }
    const latest = items[0];
    const files = latest.files;
    const img = files.find(f=>f.match(/\.jpg|\.png|out/)) || files[0];
    const video = files.find(f=>f.endsWith('.mp4')) || null;
    let html = '';
    if(img){ const url = `/functions/v1/get-file?path=${encodeURIComponent(latest.path+'/'+img)}`; html += `<div><img src="${url}" style="max-width:240px"></div>`; }
    if(video){ const vurl = `/functions/v1/get-file?path=${encodeURIComponent(latest.path+'/'+video)}`; html += `<div><a href="${vurl}" target="_blank">Pobierz wideo</a></div>`; }
    html += `<div class="small dim">Folder: ${latest.path}</div>`;
    el('last-result').innerHTML = html;
  }catch(e){console.warn('list outputs failed', e)}
}

function setCountButtons(){
  document.querySelectorAll('.count-btn').forEach(b=>{
    b.addEventListener('click', ()=>{
      const n = parseInt(b.dataset.count||'1'); document.querySelectorAll('.count-btn').forEach(x=>x.classList.remove('active')); b.classList.add('active'); el('generate-btn').textContent = `Generuj ${n} short`; el('generate-btn').dataset.count = n;
    });
  });
}

function bind(){
  el('refresh-status').addEventListener('click', refreshStatus);
  el('save-config').addEventListener('click', ()=>{saveConfig(); refreshStatus();});
  el('generate-btn').addEventListener('click', ()=>{ const n = parseInt(el('generate-btn').dataset.count||'1'); enqueue(n); });
  setCountButtons();
}

async function init(){
  loadConfig(); bind(); await refreshStatus(); await loadVoices(); updateLastResult();
  setInterval(refreshStatus, 15000);
}

document.addEventListener('DOMContentLoaded', init);
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
