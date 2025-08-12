let FB_TOKEN = null;
const api = {
  assets: '/.netlify/functions/assets',
  listPosts: '/.netlify/functions/list_posts',
  setup: '/.netlify/functions/setup',
  optimize: '/.netlify/functions/optimize',
};

const postsDiv = document.getElementById('posts');
const logEl = document.getElementById('log');
const chartEl = document.getElementById('chart');

function log(msg) {
  const t = new Date().toLocaleTimeString();
  logEl.textContent = `[${t}] ` + msg + "\n" + logEl.textContent;
}


async function fetchAssets() {
  if (!FB_TOKEN) { alert('Login with Facebook first'); return; }
  const res = await fetch(api.assets, { headers: { 'X-FB-Token': FB_TOKEN } });
  const data = await res.json();
  if (data.error) { alert(data.error); return; }
  const adSel = document.getElementById('ad_account');
  const pgSel = document.getElementById('page_id');
  adSel.innerHTML = ''; pgSel.innerHTML = '';
  (data.ad_accounts || []).forEach(a => {
    const opt = document.createElement('option'); opt.value = a.id; opt.textContent = `${a.name} (${a.currency})`; adSel.appendChild(opt);
  });
  (data.pages || []).forEach(p => {
    const opt = document.createElement('option'); opt.value = p.id; opt.textContent = p.name; pgSel.appendChild(opt);
  });
}

document.getElementById('btnFb').addEventListener('click', async () => {
  // Simple OAuth implicit flow via popup
  const APP_ID = window.FB_APP_ID || prompt('Enter your Facebook App ID');
  const redirect = window.location.origin + '/';
  const scope = [
    'ads_management',
    'ads_read',
    'pages_read_engagement',
    'pages_read_user_content',
    'pages_manage_ads',
    'public_profile'
  ].join(',');
  const authUrl = `https://www.facebook.com/v23.0/dialog/oauth?client_id=${APP_ID}&redirect_uri=${encodeURIComponent(redirect)}&response_type=token&scope=${encodeURIComponent(scope)}`;
  const w = window.open(authUrl, '_blank', 'width=520,height=700');
  const timer = setInterval(() => {
    try {
      if (!w || w.closed) { clearInterval(timer); return; }
      const href = w.location.href;
      if (href.startsWith(redirect) && href.includes('#access_token=')) {
        const hash = new URL(href).hash.substring(1);
        const params = new URLSearchParams(hash);
        FB_TOKEN = params.get('access_token');
        w.close(); clearInterval(timer);
        localStorage.setItem('fb_token', FB_TOKEN);
        alert('✅ Facebook connected'); fetchAssets();
      }
    } catch (e) { /* cross-origin until redirected back */ }
  }, 500);
});

// Auto-pick token if present
(function(){
  const t = localStorage.getItem('fb_token');
  if (t) { FB_TOKEN = t; fetchAssets(); }
})();


document.getElementById('btnLoad').addEventListener('click', async () => {
  postsDiv.innerHTML = 'Loading…';
  const token = document.getElementById('admintoken').value.trim();
  const token = document.getElementById('admintoken').value.trim();
  const pageId = document.getElementById('page_id').value;
  if (!FB_TOKEN) { alert('Login with Facebook first'); return; }
  if (!pageId) { alert('Choose a Page'); return; }
  const res = await fetch(api.listPosts + `?page_id=${pageId}`, { headers: Object.assign({ 'X-FB-Token': FB_TOKEN }, token ? { 'Authorization': `Bearer ${token}` } : {}) });
  const data = await res.json();
  if (data.error) { postsDiv.innerHTML = 'Error: ' + data.error; return; }
  postsDiv.innerHTML = '';
  (data.posts || []).forEach((p, i) => {
    const row = document.createElement('label');
    row.className = 'post';
    row.innerHTML = `
      <input type="checkbox" data-id="${p.id}" />
      <div style="flex:1">
        <div style="font-weight:700">${(p.short || '(no text)')}</div>
        <time>${p.created}</time>
      </div>
      <a href="${p.url}" target="_blank">open</a>
    `;
    postsDiv.appendChild(row);
  });
});

document.getElementById('btnSetup').addEventListener('click', async () => {
  const chosen = Array.from(postsDiv.querySelectorAll('input[type=checkbox]:checked')).map(x => x.getAttribute('data-id'));
  if (chosen.length === 0) { alert('اختر بوستات لعمل sponsor'); return; }
  const payload = {
    posts: chosen,
    msg_min: Number(document.getElementById('msg_min').value || 10),
    eng_min: Number(document.getElementById('eng_min').value || 10)
  };
  log('Launching setup…');
  const token = document.getElementById('admintoken').value.trim();
  const adAcc = document.getElementById('ad_account').value;
  const pageId = document.getElementById('page_id').value;
  if (!FB_TOKEN) { alert('Login with Facebook first'); return; }
  payload.ad_account_id = adAcc; payload.page_id = pageId; payload.brand = 'Corella Store'; payload.whatsapp_number = prompt('WhatsApp number (216...)', '2165xxxxxxx');
  const res = await fetch(api.setup, { method:'POST', headers:Object.assign({'Content-Type':'application/json','X-FB-Token': FB_TOKEN}, token ? {'Authorization': `Bearer ${token}`} : {}), body: JSON.stringify(payload) });
  const data = await res.json();
  if (data.error) { alert(data.error); log('Error: ' + data.error); return; }
  log('✅ Setup OK');
  console.log(data);
  alert('Setup done. Campaigns activated.');
});

let chart;
function drawChart(msgKpi, engKpi) {
  if (chart) chart.destroy();
  chart = new Chart(chartEl.getContext('2d'), {
    type: 'bar',
    data: {
      labels: ['Messages CPA', 'Engagement CPE'],
      datasets: [{
        label: 'Cost (DT)',
        data: [msgKpi ?? 0, engKpi ?? 0]
      }]
    },
    options: { responsive:true, plugins:{ legend:{ display:false } }, scales:{ y:{ beginAtZero:true } } }
  });
}

document.getElementById('btnOptimize').addEventListener('click', async () => {
  const payload = {
    msg_min: Number(document.getElementById('msg_min').value || 10),
    msg_max: Number(document.getElementById('msg_max').value || 200),
    msg_target_cpa: Number(document.getElementById('msg_target').value || 2.5),
    eng_min: Number(document.getElementById('eng_min').value || 10),
    eng_max: Number(document.getElementById('eng_max').value || 150),
    eng_target_cpe: Number(document.getElementById('eng_target').value || 0.2),
  };
  log('Optimizing…');
  const token = document.getElementById('admintoken').value.trim();
  const adAcc = document.getElementById('ad_account').value;
  if (!FB_TOKEN) { alert('Login with Facebook first'); return; }
  payload.ad_account_id = adAcc; payload.brand = 'Corella Store';
  const res = await fetch(api.optimize, { method:'POST', headers:Object.assign({'Content-Type':'application/json','X-FB-Token': FB_TOKEN}, token ? {'Authorization': `Bearer ${token}`} : {}), body: JSON.stringify(payload) });
  const data = await res.json();
  if (data.error) { alert(data.error); log('Error: ' + data.error); return; }
  const m = data.messages || {}; const e = data.engagement || {};
  log(`Messages: spend=${(m.spend||0).toFixed(2)}, convos=${m.qty||0}, CPA=${m.kpi ? m.kpi.toFixed(3) : '—'} | ${m.old_budget?.toFixed(2)}→${m.new_budget?.toFixed(2)} DT/day`);
  log(`Engagement: spend=${(e.spend||0).toFixed(2)}, eng=${e.qty||0}, CPE=${e.kpi ? e.kpi.toFixed(3) : '—'} | ${e.old_budget?.toFixed(2)}→${e.new_budget?.toFixed(2)} DT/day`);
  drawChart(m.kpi, e.kpi);
});

// ---- Chat ----
const chatDiv = document.getElementById('chat');
const chatInput = document.getElementById('chatmsg');
const btnSend = document.getElementById('btnSend');
let history = [{ role:'assistant', content: 'مرحبا! أنا Corella Copilot. شنوّة تحب تعمل اليوم؟ (setup, optimize, كتابة نصوص، أفكار عروض...)' }];

function renderChat(){
  chatDiv.innerHTML = '';
  history.forEach(m => {
    const row = document.createElement('div');
    row.className = 'msg';
    row.innerHTML = `<div class="who">${m.role}</div><div class="text">${m.content}</div>`;
    chatDiv.appendChild(row);
  });
  chatDiv.scrollTop = chatDiv.scrollHeight;
}
renderChat();

async function sendChat(){
  const text = chatInput.value.trim();
  if (!text) return;
  history.push({ role:'user', content: text });
  renderChat();
  chatInput.value='';
  const token = document.getElementById('admintoken').value.trim();
  const adAcc = document.getElementById('ad_account').value;
  const pageId = document.getElementById('page_id').value;

  const res = await fetch('/.netlify/functions/chat', {
    method:'POST',
    headers: Object.assign(
      { 'Content-Type':'application/json', 'X-FB-Token': FB_TOKEN || '' },
      token ? { 'Authorization': `Bearer ${token}` } : {}
    ),
    body: JSON.stringify({
      messages: history,
      ad_account_id: adAcc || null,
      page_id: pageId || null,
      brand: 'Corella Store'
    })
  });
  const data = await res.json();
  if (data.error) {
    history.push({ role:'assistant', content: '❌ ' + data.error });
  } else {
    history.push({ role:'assistant', content: data.message || '(ok)' });
    if (Array.isArray(data.tools) && data.tools.length){
      history.push({ role:'assistant', content: '🔧 Tools run: ' + data.tools.map(t=>t.name).join(', ') });
    }
  }
  renderChat();
}
btnSend.addEventListener('click', sendChat);
chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });
