// Offline verification only. Never imports Python, calls production or uses a personal profile.
import { createServer } from 'node:http';
import { mkdtemp, mkdir, readFile, writeFile, realpath, access } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import assert from 'node:assert/strict';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const chromePath = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const CSP = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'; object-src 'none'";
const token = 'offline-fixture-not-a-production-token';
let status = { connected: true, empty: false, count: 2, revision: 1 };
const requestPlans = [];
const hostile = '**Salida ficticia**\nsegunda línea\n\n<img src="https://example.invalid/private">\n\n![Imagen ficticia](https://example.invalid/image)\n\n[Enlace ficticio](javascript:alert(1))';
const signals = { exact_previous: false, same_opening: false, shared_trigrams: 0, guidance_trigrams: 0 };
const posts = [], external = [], runtimeErrors = [], checks = [], modalObservations = [];
let lastBackdropPoint = null;
let failRaw = false, failBootstrap = false, rawBody, origin, browser, socket, server, out, stopped = false;
let step = 'setup', selector = '';
let releaseRaw;
const rawGate = new Promise(resolve => { releaseRaw = resolve; });
const deadline = Date.now() + 100000;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const pending = new Map();
let nextId = 0;
function decode(text) {
  try { return JSON.parse(text); } catch { throw new Error('Invalid fixture/CDP JSON'); }
}
async function wait(test, name) {
  step = name;
  const stepDeadline = Math.min(Date.now() + 7000, deadline - 5000);
  while (Date.now() < stepDeadline) {
    if (await test()) return;
    await delay(80);
  }
  throw new Error(`Deadline: ${name}`);
}
function send(method, params = {}, timeoutMs = 7000) {
  if (!socket || socket.readyState !== WebSocket.OPEN) return Promise.reject(new Error('CDP unavailable'));
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, timeoutMs);
    pending.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression, timeoutMs = 7000) {
  const answer = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true }, timeoutMs);
  if (answer.exceptionDetails) throw new Error('Fixture expression failed');
  return answer.result?.value;
}
async function mouseClick(x, y) {
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y });
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', button: 'left', buttons: 1, clickCount: 1, x, y });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', button: 'left', buttons: 0, clickCount: 1, x, y });
}
async function clickTarget(css, label) {
  step = 'activate visible control'; selector = label ? `${css} / ${label}` : css;
  // Scroll only. Never change visibility, dispatch HTMLElement.click or set app state.
  const target = `(() => [...document.querySelectorAll(${JSON.stringify(css)})].find(e =>
    ${label ? `(e.getAttribute('aria-label') || e.textContent.trim()) === ${JSON.stringify(label)} &&` : ''}
    e.getClientRects().length && getComputedStyle(e).visibility === 'visible'))()`;
  await wait(() => evaluate(`!!${target}`), `find control: ${selector}`);
  const position = await evaluate(`(() => {
    const e = ${target};
    if (!e || e.disabled) return null;
    e.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
    const r = e.getBoundingClientRect();
    const x = Math.max(1, Math.min(innerWidth - 1, r.x + r.width / 2));
    const y = Math.max(1, Math.min(innerHeight - 32, r.y + r.height / 2));
    const hit = document.elementFromPoint(x, y);
    return e === hit || e.contains(hit) ? { x, y } : null;
  })()`);
  assert.ok(position, 'Control disabled or occluded');
  await mouseClick(position.x, position.y);
}
async function click(text, role = 'button') {
  await clickTarget(role === 'tab' ? '[role="tab"]' : 'button,summary', text);
}
async function fill(id, value) {
  await clickTarget(`#${id}`);
  step = 'fill fictional text'; selector = `#${id}`;
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'a', code: 'KeyA', modifiers: 2, windowsVirtualKeyCode: 65 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'a', code: 'KeyA', modifiers: 2 });
  await send('Input.insertText', { text: value });
}
async function focusedAndUnobscured(name) {
  step = name;
  assert.equal(await evaluate(`(() => {
    const e = document.activeElement; if (!e || e === document.body) return false;
    const r = e.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0 || r.top < 0 || r.bottom > innerHeight - 28 || r.left < 0 || r.right > innerWidth) return false;
    const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
    return e === hit || e.contains(hit);
  })()`), true, 'Focused control is not visible and unobscured');
}
async function composerOpacity(name) {
  step = name; selector = '#raw-history, #raw-disclosure';
  assert.equal(await evaluate(`(() => {
    const button = document.querySelector('button[aria-label="Generar borrador"]');
    const input = document.getElementById('raw-history'), disclosure = document.getElementById('raw-disclosure');
    if (!button?.disabled || !input || input.disabled || !disclosure) return false;
    for (const element of [input, disclosure]) {
      for (let ancestor = element; ancestor; ancestor = ancestor.parentElement) {
        if (Number(getComputedStyle(ancestor).opacity) !== 1) return false;
      }
    }
    return true;
  })()`), true, 'Editable composer/disclosure must retain opacity 1');
  await checkpoint(name);
}
async function openObservedModal(label) {
  step = 'capture modal initiating button'; selector = `button / ${label}`;
  lastBackdropPoint = null;
  assert.equal(await evaluate(`(() => {
    window.__modalTrigger = [...document.querySelectorAll('button')].find(e =>
      (e.getAttribute('aria-label') || e.textContent.trim()) === ${JSON.stringify(label)} && e.getClientRects().length);
    return Boolean(window.__modalTrigger?.isConnected && !window.__modalTrigger.disabled);
  })()`), true);
  await click(label);
}
async function modalReady(name) {
  selector = '[role=dialog] / visible stable rectangle and initial focus';
  await wait(() => evaluate(`(async () => {
    const dialog = document.querySelector('[role=dialog]');
    if (!dialog) return false;
    const sample = () => {
      const r = dialog.getBoundingClientRect(), s = getComputedStyle(dialog);
      return { rect: [r.x,r.y,r.width,r.height], visible: r.width>0 && r.height>0
        && s.visibility==='visible' && s.display!=='none' && Number(s.opacity)>0,
        focused: dialog.contains(document.activeElement) };
    };
    const before = sample();
    // Observe deferred focus and paint; never manufacture readiness or replay input.
    await new Promise(resolve => setTimeout(resolve, 0));
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const after = sample();
    return dialog.isConnected && before.visible && after.visible && after.focused
      && JSON.stringify(before.rect)===JSON.stringify(after.rect);
  })()`, 2000), `${name}: modal ready`);
}
async function closeObservedModal(name, dispatch) {
  const before = posts.length;
  step = `${name}: single input dispatch`; selector = dispatch === 'outside' ? 'observed overlay interior point' : '[role=dialog] / Escape';
  if (dispatch === 'outside') await mouseClick(lastBackdropPoint.x, lastBackdropPoint.y);
  else await key('Escape', 'Escape');
  selector = '[role=dialog]';
  await wait(() => evaluate('!document.querySelector("[role=dialog]")'), `${name}: dialog disappearance`);
  selector = 'exact observed initiating button';
  await wait(() => evaluate('Boolean(window.__modalTrigger?.isConnected && document.activeElement===window.__modalTrigger)'), `${name}: exact trigger focus return`);
  selector = 'observed initiating button / visibility and hit test';
  await focusedAndUnobscured(`${name}: visible hit target`);
  step = `${name}: POST accounting`; selector = 'fixture POST count';
  assert.equal(posts.length, before);
  await checkpoint(`${name}: closed without POST`);
}
async function modalChecks(name) {
  await modalReady(name);
  await key('Tab', 'Tab');
  assert.equal(await evaluate('document.querySelector("[role=dialog]").contains(document.activeElement)'), true, 'Modal focus escaped');
  const before = await evaluate('({ x: scrollX, y: scrollY, locked: getComputedStyle(document.body).overflow === "hidden", width: innerWidth, height: innerHeight })');
  assert.equal(before.locked, true, 'Body scroll lock missing');
  await send('Input.dispatchMouseEvent', { type: 'mouseWheel', x: before.width - 4, y: before.height / 2, deltaX: 0, deltaY: 500 });
  await delay(120);
  assert.deepEqual(await evaluate('({x: scrollX, y: scrollY})'), { x: before.x, y: before.y }, 'Background scrolled through modal');
  await checkpoint(name);
}
async function observeModalGeometry(point = null, timeoutMs = 2000) {
  return evaluate(`(() => {
    const dialog = document.querySelector('[role=dialog]');
    const overlay = [...document.querySelectorAll('.dialog-overlay,[data-slot="sheet-overlay"]')]
      .find(e => e.getClientRects().length && getComputedStyle(e).visibility==='visible');
    const rect = e => { if (!e) return null; const r=e.getBoundingClientRect();
      return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height}; };
    const d=rect(dialog), o=rect(overlay), s=overlay && getComputedStyle(overlay);
    const width=document.documentElement.clientWidth, height=document.documentElement.clientHeight;
    let point=${JSON.stringify(point)};
    if (!point && d && o) {
      const left=Math.max(0,o.x), right=Math.min(width,o.right), top=Math.max(0,o.y), bottom=Math.min(height,o.bottom);
      const regions=[
        [left,top,Math.min(right,d.x),bottom], [Math.max(left,d.right),top,right,bottom],
        [left,top,right,Math.min(bottom,d.y)], [left,Math.max(top,d.bottom),right,bottom]
      ].filter(([l,t,r,b]) => r-l>4 && b-t>4).sort((a,b) => (b[2]-b[0])*(b[3]-b[1])-(a[2]-a[0])*(a[3]-a[1]));
      if (regions.length) { const [l,t,r,b]=regions[0]; point={x:(l+r)/2,y:(t+b)/2}; }
    }
    const hit=point && document.elementFromPoint(point.x,point.y), trigger=window.__modalTrigger;
    const tag=hit?.tagName.toLowerCase(), role=hit?.getAttribute('role');
    const inside=Boolean(point && o && point.x>Math.max(0,o.x) && point.x<Math.min(width,o.right)
      && point.y>Math.max(0,o.y) && point.y<Math.min(height,o.bottom));
    const outside=Boolean(point && d && (point.x<d.x || point.x>d.right || point.y<d.y || point.y>d.bottom));
    return {dialog:d,overlay:o,client:{width,height},inner:{width:innerWidth,height:innerHeight},point,
      hitTag:['body','button','input','textarea','div','section'].includes(tag)?tag:'other',
      hitRole:['dialog','button','textbox','tab'].includes(role)?role:'other',isOverlay:Boolean(overlay && hit===overlay),
      overlayVisible:Boolean(s && s.visibility==='visible' && s.display!=='none' && Number(s.opacity)>0),
      pointerEventsAuto:Boolean(s && s.pointerEvents==='auto'),inside,outside,
      dialogPresent:Boolean(dialog),triggerConnected:Boolean(trigger?.isConnected),triggerDisabled:Boolean(trigger?.disabled),
      exactFocusMatch:Boolean(trigger && document.activeElement===trigger)};
  })()`, timeoutMs);
}
async function outsideModal(name) {
  await modalReady(name);
  step = `${name}: geometry and hit test`; selector = '.dialog-overlay,[data-slot="sheet-overlay"] / interior region center';
  const observed = await observeModalGeometry();
  lastBackdropPoint = observed.point;
  modalObservations.push({phase:step,...observed});
  assert.ok(observed.point && observed.inside && observed.outside && observed.isOverlay
    && observed.overlayVisible && observed.pointerEventsAuto, 'Live overlay interior must be hit-testable');
  await closeObservedModal(name, 'outside');
}
async function key(key, code, modifiers = 0) {
  const character = key === 'Enter' && (modifiers === 0 || modifiers === 8) ? { text: '\r', unmodifiedText: '\r' } : {};
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key, code, modifiers, windowsVirtualKeyCode: key === 'Escape' ? 27 : key === 'Tab' ? 9 : 13, ...character });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key, code, modifiers });
}
async function screenshot(name) {
  step = `screenshot: ${name}`;
  await evaluate(`Promise.all(document.getAnimations().filter(a => a.effect?.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})))`);
  const result = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  await writeFile(join(out, `${name}.png`), Buffer.from(result.data, 'base64'), { flag: 'wx' });
}
async function checkpoint(name) {
  step = name;
  const state = await evaluate(`({ violations: window.__fixtureViolations, storage: localStorage.length + sessionStorage.length, cookies: document.cookie, styles: document.querySelectorAll('style').length, overflow: document.documentElement.scrollWidth > innerWidth + 1 })`);
  assert.deepEqual(state.violations, [], `${name}: CSP violations`);
  assert.equal(state.storage, 0); assert.equal(state.cookies, ''); assert.equal(state.styles, 0);
  assert.equal(state.overflow, false, `${name}: horizontal overflow`);
  checks.push(name);
}
async function serve(req, res) {
  res.setHeader('Content-Security-Policy', CSP);
  res.setHeader('Cache-Control', 'no-store');
  res.setHeader('Referrer-Policy', 'no-referrer');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  const path = req.url;
  const json = (body, code = 200) => { res.writeHead(code, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(body)); };
  // Count rejected deliveries too, before validating their method-specific payload.
  if (req.method === 'POST') posts.push({ path, fixture: true });
  assert.equal(req.headers.host, origin.slice('http://'.length));
  if (req.method === 'POST') {
    assert.equal(req.headers.origin, origin);
    let text = '';
    for await (const chunk of req) { text += chunk; if (text.length > 200000) { json({}, 413); return; } }
    assert.equal(req.headers['x-csrf-token'], token);
    const body = decode(text);
    const expected = requestPlans.shift();
    assert.ok(expected, 'Unplanned fixture POST');
    assert.equal(path, expected.path);
    assert.deepEqual(body, expected.body);
    if (path === '/api/raw-draft') {
      assert.deepEqual(Object.keys(body).sort(), ['consent', 'history']); assert.equal(body.consent, true);
      rawBody = body;
      if (!failRaw) await rawGate;
      return failRaw ? json({ error: 'Fallo ficticio' }, 502) : json({ result: { type: 'dm', text: hostile }, retrieval: { status: 'supplied', count: 2 }, revision: 1 });
    }
    if (path === '/api/demo') {
      assert.deepEqual(body, {});
      return json({ mode: 'simulated', drafts: { current: 'Borrador ficticio A', editorial: 'Borrador ficticio B' }, signals: { current: signals, editorial: signals } });
    }
    return json({}, 404);
  }
  if (req.method !== 'GET') return json({}, 405);
  if (path === '/api/bootstrap') return failBootstrap ? json({ error: 'Fixture offline' }, 503) : json({ app: 'tato-local', protocol: 1, csrf_token: token, model: 'unknown', effort: 'unknown' });
  if (path === '/api/auth/status') return json(status);
  if (path === '/api/auth/persistence') return json({}, 404); // Planned old-backend compatibility.
  if (path === '/api/context') return json({ csrf_token: token, model: 'unknown', effort: 'unknown', case: 'offline-fixture', phase: 'brecha', messages: [{ role: 'assistant', text: 'Pregunta ficticia' }, { role: 'user', text: 'Contexto ficticio' }], guidance: { positive_voice: 'Orientación ficticia, no aprobada.', negative_repetition: 'Sin evidencia de mejora.' } });
  if (path === '/assets/fixture-banner.css') {
    res.writeHead(200, { 'Content-Type': 'text/css' });
    return res.end('#fixture-banner{display:block;color:#ddd0a9;font:10px/14px system-ui;margin-top:2px}');
  }
  if (path === '/favicon.ico') { res.writeHead(204); return res.end(); }
  if (path === '/' || /^\/assets\/[A-Za-z0-9_-]+\.(js|css)$/.test(path)) {
    const file = join(root, 'dist', path === '/' ? 'index.html' : path.slice(1));
    assert.equal(resolve(await realpath(file)), resolve(file), 'No symlinks in fixture assets');
    let body = await readFile(file);
    if (path === '/') body = Buffer.from(body.toString().replace('</head>', '<link rel="stylesheet" href="/assets/fixture-banner.css"></head>'));
    res.writeHead(200, { 'Content-Type': path === '/' ? 'text/html' : path.endsWith('.js') ? 'text/javascript' : 'text/css' });
    return res.end(body);
  }
  json({}, 404);
}
async function cleanup() {
  if (stopped) return; stopped = true;
  if (socket?.readyState === WebSocket.OPEN) {
    try { await send('Browser.close'); } catch { /* Owned process may already be closed. */ }
    socket.close();
  }
  if (browser && browser.exitCode === null) {
    // Only this child's handle is eligible; never process-name/PID discovery.
    browser.kill();
  }
  for (const p of pending.values()) { clearTimeout(p.timer); p.reject(new Error('Fixture closed')); }
  pending.clear();
  server?.closeAllConnections();
  if (server?.listening) await new Promise(resolve => server.close(resolve));
  // Retain the exclusively-owned temporary profile for explicit inspection; no deletion.
}
let watchdog;
try {
  await access(chromePath); await access(join(root, 'dist/index.html'));
  out = await mkdtemp(join(tmpdir(), 'tato-ui-fixture-'));
  const profile = join(out, 'chrome-profile'); await mkdir(profile);
  server = createServer((req, res) => { serve(req, res).catch(() => { runtimeErrors.push('Fixture response failed'); res.writeHead(500); res.end('Fixture failure'); }); });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const port = server.address().port; assert.notEqual(port, 8765);
  origin = `http://127.0.0.1:${port}`;
  browser = spawn(chromePath, ['--headless=new', '--remote-debugging-port=0', '--remote-debugging-address=127.0.0.1', `--user-data-dir=${profile}`, '--no-first-run', '--no-default-browser-check', '--disable-extensions', '--disable-background-networking', '--disable-component-update', '--disable-sync', '--disable-default-apps', '--disable-domain-reliability', '--metrics-recording-only', '--no-proxy-server', '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1', 'about:blank'], { stdio: ['ignore', 'ignore', 'pipe'] });
  let endpoint = '', spawnError;
  browser.on('error', error => { spawnError = error; });
  browser.stderr.on('data', chunk => { endpoint += chunk.toString(); });
  watchdog = setTimeout(() => { process.exitCode = 1; cleanup().catch(() => {}); }, 105000);
  await wait(() => { if (spawnError) throw spawnError; return /DevTools listening on (ws:\/\/127\.0\.0\.1:\d+\/[^\s]+)/.test(endpoint); }, 'Chrome endpoint');
  const browserWs = endpoint.match(/DevTools listening on (ws:\/\/127\.0\.0\.1:\d+\/[^\s]+)/)[1];
  const debugOrigin = browserWs.replace(/^ws:/, 'http:').split('/devtools/')[0];
  const targets = await (await fetch(`${debugOrigin}/json/list`)).json();
  const target = targets.find(t => t.type === 'page' && t.url === 'about:blank');
  assert.ok(target && target.webSocketDebuggerUrl.startsWith('ws://127.0.0.1:'));
  socket = new WebSocket(target.webSocketDebuggerUrl);
  socket.addEventListener('message', event => {
    const message = decode(event.data);
    if (message.id) {
      const p = pending.get(message.id); if (!p) return;
      clearTimeout(p.timer); pending.delete(message.id);
      if (message.error) p.reject(new Error('CDP command rejected')); else p.resolve(message.result);
    } else if (message.method === 'Fetch.requestPaused') {
      const { request, requestId } = message.params;
      const local = request.url.startsWith(`${origin}/`);
      if (!local) external.push('Blocked external page request');
      send(local ? 'Fetch.continueRequest' : 'Fetch.failRequest', local ? { requestId } : { requestId, errorReason: 'BlockedByClient' }).catch(() => runtimeErrors.push('Request interception failed'));
    } else if (message.method === 'Runtime.exceptionThrown') runtimeErrors.push('Browser runtime exception');
  });
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }); });
  await send('Page.enable'); await send('Runtime.enable');
  await send('Fetch.enable', { patterns: [{ urlPattern: '*' }] });
  await send('Page.addScriptToEvaluateOnNewDocument', { source: `window.__fixtureViolations=[];
    document.addEventListener('securitypolicyviolation',e=>window.__fixtureViolations.push({directive:e.violatedDirective,blocked:e.blockedURI}));
    new MutationObserver(()=>{const title=document.querySelector('.header-title');if(title && !document.getElementById('fixture-banner')){
      const label=document.createElement('small');label.id='fixture-banner';label.textContent='FIXTURES OFFLINE · SIN MODELOS, AUTH NI DB REALES';title.append(label);
    }}).observe(document,{childList:true,subtree:true});` });
  await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'no-preference' }] });
  await send('Page.navigate', { url: origin });
  await wait(() => evaluate('!!document.getElementById("raw-history") && document.body.textContent.includes("Servidor local conectado")'), 'mount');
  assert.equal(posts.length, 0);
  await composerOpacity('empty composer opacity'); await screenshot('desktop-empty');
  await click('Alternar navegación');
  await wait(() => evaluate('!!document.querySelector("[data-slot=sidebar][data-state=collapsed]")'), 'desktop collapsed sidebar');
  assert.equal(await evaluate(`(() => {
    const tabs = [...document.querySelectorAll('[role="tab"]')];
    return tabs.length === 3 && tabs.every(e => e.title === e.textContent.trim()
      && e.title.length > 0 && getComputedStyle(e.querySelector('.nav-label')).display === 'none'
      && e.getBoundingClientRect().width > 0);
  })()`), true, 'Collapsed tabs require accessible title labels');
  await screenshot('desktop-collapsed'); await checkpoint('collapsed sidebar labels');
  await click('Alternar navegación');
  const history = 'Historial completamente ficticio\nsegunda línea 🪁';
  await fill('raw-history', history);
  await send('Input.insertText', { text: '\n' }); // Native text editing only, never form submission.
  await key('Enter', 'Enter', 8);
  assert.equal(posts.length, 0);
  const unchanged = await evaluate('document.getElementById("raw-history").value');
  await click('Biblioteca');
  await wait(() => evaluate('document.body.textContent.includes("2 criterios disponibles")'), 'library status');
  assert.equal(await evaluate('document.querySelectorAll("#editorial-email").length'), 0);
  assert.equal(await evaluate('document.getElementById("raw-history").value'), unchanged);
  await screenshot('desktop-library'); await checkpoint('library CSP');
  await click('Privacidad y límites'); await click('Criterios y fuentes');
  assert.equal(await evaluate(`document.querySelectorAll('.raw-composer details').length`), 0);
  await click('Cerrar biblioteca');
  status = {connected:false,empty:false,count:0,revision:2};
  await click('Biblioteca');
  await wait(() => evaluate('!!document.getElementById("editorial-email")'), 'fictional disconnected form');
  await fill('editorial-email', 'fictional@example.invalid');
  await fill('editorial-password', 'fictional-unused-password');
  await click('Cerrar biblioteca');
  await click('Biblioteca');
  await wait(() => evaluate('!!document.getElementById("editorial-email")'), 'library reopened');
  assert.equal(await evaluate('document.getElementById("editorial-email").value + document.getElementById("editorial-password").value'), '');
  assert.equal(await evaluate('document.getElementById("raw-history").value'), unchanged);
  await click('Cerrar biblioteca');
  assert.equal(posts.length, 0);
  requestPlans.push({path:'/api/raw-draft',body:{history:unchanged,consent:true}});
  await clickTarget('#raw-history'); await key('Enter','Enter');
  await wait(() => posts.length === 1, 'raw fixture held response');
  await composerOpacity('loading composer opacity');
  assert.equal(await evaluate(`!!document.querySelector('.generation-mark svg') && !document.querySelector('.raw-draft-scroll')`), true);
  await screenshot('desktop-loading');
  releaseRaw();
  await wait(() => evaluate('document.body.textContent.includes("Salida ficticia")'), 'raw fixture output');
  assert.equal(posts.length, 1); assert.equal(rawBody.history, unchanged);
  assert.equal(await evaluate('document.getElementById("raw-history").value'), unchanged);
  assert.equal(await evaluate('document.querySelectorAll(".static-markdown img,.static-markdown iframe,.static-markdown a[href],input[type=file]").length'), 0);
  assert.equal(await evaluate('document.querySelector(".static-markdown strong").textContent'), 'Salida ficticia');
  step = 'scroll actual draft into view'; selector = '[aria-label="DM para revisar"]';
  await evaluate(`document.querySelector('section[aria-label="DM para revisar"]').scrollIntoView({ block: 'center', behavior: 'instant' })`);
  assert.equal(await evaluate(`(() => {
    const body = document.querySelector('.static-markdown');
    const copy = [...document.querySelectorAll('button')].find(e => e.textContent.trim() === 'Copiar DM');
    return [body, copy].every(e => { const r = e?.getBoundingClientRect(); return r && r.height > 0 && r.top >= 0 && r.bottom <= innerHeight - 28; });
  })()`), true, 'Actual Markdown body and Copy must fit screenshot');
  await screenshot('desktop-result'); await checkpoint('raw Markdown body and copy visible / CSP');
  failRaw = true;
  requestPlans.push({path:'/api/raw-draft',body:{history:unchanged,consent:true}});
  await click('Generar borrador');
  await wait(() => evaluate('!!document.querySelector("[role=alert]")'), 'fixture error');
  assert.equal(posts.length, 2);
  await checkpoint('fixture error without retry');
  failBootstrap = true;
  await click('Reconectar');
  await wait(() => evaluate('document.body.textContent.includes("Sin conexión local")'), 'fixture disconnected');
  await composerOpacity('disconnected composer opacity');
  failBootstrap = false;
  await click('Reconectar');
  await wait(() => evaluate('document.body.textContent.includes("Servidor local conectado")'), 'reconnect');
  assert.equal(posts.length, 2);
  assert.equal(await evaluate('document.getElementById("raw-history").value'), unchanged);
  await checkpoint('reconnect preserves history without POST replay');
  await send('Page.reload');
  await wait(() => evaluate('!!document.getElementById("raw-history") && document.body.textContent.includes("Servidor local conectado")'), 'reload');
  assert.equal(posts.length, 2); assert.equal(await evaluate('document.getElementById("raw-history").value'), '');
  await checkpoint('reload clears memory without POST');
  await click('Revisión avanzada', 'tab');
  await wait(() => evaluate('!!document.getElementById("real-history")'), 'advanced tab activated by pointer');
  await fill('real-history', 'Prospecto: mensaje ficticio\nTato: respuesta ficticia\nProspecto: otro mensaje');
  await click('Revisar conversación');
  await screenshot('desktop-advanced');
  await openObservedModal('Editar mensaje 1');
  await modalChecks('review editor focus / CSP');
  await closeObservedModal('review editor Escape', 'escape');
  assert.equal(posts.length, 2);
  await clickTarget('.optional-panel .review-label input');
  await click('Organizar con Codex');
  await modalChecks('optional organization separate consent');
  assert.equal(await evaluate('document.querySelector("[role=dialog]").textContent.includes("No genera un DM después")'), true);
  await click('Cancelar');
  await wait(() => evaluate('!document.querySelector("[role=dialog]")'), 'organization canceled');
  assert.equal(posts.length, 2);
  await clickTarget('.draft-panel .review-label input');
  await openObservedModal('Generar respuesta');
  assert.equal(posts.length, 2);
  await modalChecks('advanced modal CSP / focus / scroll lock'); await screenshot('desktop-consent');
  await closeObservedModal('advanced Escape', 'escape');
  assert.equal(posts.length, 2);
  await openObservedModal('Generar respuesta');
  await outsideModal('advanced outside-click dismissal');
  assert.equal(posts.length, 2);
  await click('Comparador sintético', 'tab');
  await wait(() => evaluate('document.body.textContent.includes("Contexto ficticio")'), 'synthetic context');
  requestPlans.push({path:'/api/demo',body:{}});
  await click('Ver demo simulada');
  await wait(() => evaluate('document.body.textContent.includes("Borrador ficticio A")'), 'demo fixtures');
  await screenshot('desktop-comparator');
  await click('Generar con Codex Pro');
  assert.equal(await evaluate('document.querySelector(".consent").textContent.includes("Se harán dos llamadas a Codex")'), true);
  assert.equal(posts.length, 3);
  assert.equal(await evaluate('[...document.querySelectorAll("button")].find(b=>b.textContent==="Confirmar dos llamadas").disabled'), true);
  await key('Escape', 'Escape'); assert.equal(posts.length, 3);
  await checkpoint('comparator CSP');
  await click('Responder conversación', 'tab');
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  await fill('raw-history', 'Historial ficticio móvil');
  await openObservedModal('Alternar navegación');
  await wait(() => evaluate('!!document.querySelector("[role=dialog]")'), 'mobile navigation');
  await modalChecks('mobile Sheet CSP / focus / scroll lock');
  await screenshot('mobile-navigation');
  await closeObservedModal('mobile Sheet Escape', 'escape');
  await openObservedModal('Alternar navegación');
  await outsideModal('mobile Sheet outside-click dismissal');
  await click('Biblioteca');
  await wait(() => evaluate('!!document.querySelector(".library-body")'), 'mobile library open');
  await clickTarget('#editorial-email');
  await focusedAndUnobscured('mobile library field focus');
  await screenshot('mobile-library'); await checkpoint('mobile library CSP / overflow');
  await click('Cerrar biblioteca');
  await wait(() => evaluate('!document.querySelector(".library-body")'), 'mobile library closed');
  assert.equal(await evaluate('document.activeElement.getAttribute("aria-label")'), 'Biblioteca');
  await focusedAndUnobscured('mobile library close focus return');
  await checkpoint('mobile library close');
  await click('Biblioteca');
  await clickTarget('#editorial-email');
  await key('Escape', 'Escape');
  await wait(() => evaluate('!document.querySelector(".library-body")'), 'mobile library Escape');
  assert.equal(await evaluate('document.activeElement.getAttribute("aria-label")'), 'Biblioteca');
  await focusedAndUnobscured('mobile library Escape focus return');
  assert.equal(await evaluate('document.getElementById("raw-history").value'), 'Historial ficticio móvil');
  assert.equal(posts.length, 3);
  await screenshot('mobile-composer'); await checkpoint('mobile composer CSP / history / no POST');
  assert.deepEqual(requestPlans, []);
  assert.deepEqual(external, []); assert.deepEqual(runtimeErrors, []);
  assert.equal(posts.filter(p => p.path === '/api/generate' || p.path.startsWith('/api/auth/')).length, 0);
  await writeFile(join(out, 'report.json'), JSON.stringify({ fixtureOnly: true, productionUsed: false, modelRequests: 0, externalRequests: external.length, posts, checks, modalObservations, CSP, screenshots: 'PNG en este directorio', profileRetained: true }, null, 2), { flag: 'wx' });
  console.log(`OFFLINE FIXTURES PASS: ${out}`);
} catch {
  process.exitCode = 1;
  console.error(`OFFLINE FIXTURES FAILED: step=${step}; selector=${selector || 'none'}`);
  if (out) {
    let focusObservation = null, failureGeometry = null, failurePNG = false;
    // Observation only: no text, DOM serialization, credentials or focus repair.
    if (socket?.readyState === WebSocket.OPEN && Date.now() < deadline) {
      try {
        focusObservation = await evaluate(`(() => {
          const trigger = window.__modalTrigger, active = document.activeElement;
          const tag = active?.tagName.toLowerCase(), role = active?.getAttribute('role');
          return { dialogPresent: Boolean(document.querySelector('[role=dialog]')),
            triggerConnected: Boolean(trigger?.isConnected), triggerDisabled: Boolean(trigger?.disabled),
            exactFocusMatch: Boolean(trigger && active === trigger),
            activeTag: ['body','button','input','textarea','div','section'].includes(tag) ? tag : 'other',
            activeRole: ['dialog','button','textbox','tab'].includes(role) ? role : 'other' };
        })()`, Math.min(1500, deadline-Date.now()));
      } catch { /* Closed diagnostics only; remote errors are never persisted. */ }
      if (Date.now() < deadline) {
        try { failureGeometry = await observeModalGeometry(lastBackdropPoint, Math.min(1500, deadline-Date.now())); }
        catch { /* Keep prior dispatch geometry if the page is unavailable. */ }
      }
      if (Date.now() < deadline) {
        try {
          const image = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }, Math.min(1500, deadline-Date.now()));
          await writeFile(join(out, 'failure-diagnostic.png'), Buffer.from(image.data, 'base64'), { flag: 'wx' });
          failurePNG = true;
        } catch { /* Failure capture is bounded and does not reposition the page. */ }
      }
    }
    await writeFile(join(out, 'failure.json'), JSON.stringify({ fixtureOnly: true, error: 'fixture-check-failed', step, selector, checks, posts, externalCount: external.length, runtimeErrorCount: runtimeErrors.length, modalObservations, failureGeometry, focusObservation, failurePNG }, null, 2), { flag: 'wx' });
    console.error(`Artifacts: ${out}`);
  }
} finally {
  clearTimeout(watchdog);
  await cleanup();
}
