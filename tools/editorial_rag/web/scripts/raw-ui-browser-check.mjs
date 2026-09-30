// RAW-only offline fixtures. Prepared for independent execution, not visual approval.
import { createServer } from 'node:http';
import { access, mkdtemp, mkdir, readFile, realpath, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';
import assert from 'node:assert/strict';

const args = process.argv.slice(2);
const mode = args.length === 0 ? 'matrix' : args.length === 1 && args[0] === '--diagnose-transport' ? 'diagnose-transport' : 'invalid';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const chromePath = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const CSP = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'; object-src 'none'";
const label = 'DEMOSTRACIÓN LOCAL — SIN IA REAL';
const history = [...('Demostración ficticia 🧭 — texto genérico, sin personas ni datos reales.\n'.repeat(350))].slice(0, 20000).join('');
const draft = '**INICIO DEL BORRADOR FICTICIO**\n\n' + 'Párrafo de demostración editorial, sin conversación real.\n\n'.repeat(200) + '**FIN DEL BORRADOR FICTICIO**';
const hostile = '**Demostración ficticia**\n\n<img src="https://example.invalid/private">\n\n![Imagen ficticia](https://example.invalid/image)\n\n[Enlace ficticio](https://example.invalid/link)';
const envelope = text => ({ result: { type: 'dm', text }, retrieval: { status: 'supplied', count: 2 }, revision: 1 });
const posts = [], interceptions = [], checks = [], captures = [], details = [], external = [], runtimeErrors = [], plans = [], authPlans = [];
let libraryConnected = true, persistenceActivated = false;
let server, browser, socket, out, origin, phase = 'setup', sequence = 0, token = '', mobile = false;
let stopped = false, watchdog, bootCount = 0, viewport, nextId = 0;
const pending = new Map();
let interactionStep = 'matrix', lastPointer = null, failurePhase = null;
let failureDiagnostic = { category: 'diagnostic', status: 'not-needed' };
const started = Date.now(), deadline = started + 140000;
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const json = JSON.stringify;
function requireCheck(value) { assert.ok(value, 'fixture assertion'); }
function runtimeIssue(category) { runtimeErrors.push({category,phase}); }
async function fetchCount() { return evaluate('window.__rawFixture.rawFetchCount'); }
async function requestDelta(name, before) {
  const clientFetchDelta=(await fetchCount())-before.client;
  const serverRequestDelta=posts.length-before.server;
  const interceptionDelta=interceptions.length-(before.interceptions ?? 0);
  const data={mode,clientFetchDelta,serverRequestDelta,interceptionDelta,observation:'counts only; cause not inferred'};
  await record(name,data);return data;
}
function parseJSON(value) {
  try { return JSON.parse(value); } catch { throw new Error('Invalid fixture JSON'); }
}
function parseURL(value) {
  try { return new URL(value); } catch { throw new Error('Invalid fixture URL'); }
}
function send(method, params = {}, timeoutMs = 7000) {
  if ((stopped && method !== 'Browser.close') || !socket || socket.readyState !== WebSocket.OPEN) return Promise.reject(new Error('CDP unavailable'));
  return new Promise((resolve, reject) => {
    const id = ++nextId;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error('CDP deadline')); }, timeoutMs);
    pending.set(id, { resolve, reject, timer });
    socket.send(json({ id, method, params }));
  });
}
async function evaluate(expression) {
  const answer = await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  requireCheck(!answer.exceptionDetails);
  return answer.result?.value;
}
async function wait(test, name) {
  phase = name;
  const end = Math.min(Date.now() + 6500, deadline);
  while (!stopped && Date.now() < end) {
    if (await test()) return;
    await delay(60);
  }
  throw new Error('Checkpoint deadline');
}
async function artifact(name, value) {
  await writeFile(join(out, name), typeof value === 'string' ? value : json(value, null, 2), { flag: 'wx' });
}
async function record(name, value) {
  checks.push(name);
  await artifact(`${String(++sequence).padStart(3, '0')}-${name}.json`, value);
}
async function click(css, text) {
  // Callers supply only static selectors/labels, never fixture history or response text.
  phase = `pointer-${interactionStep}-${text || css}`.slice(0, 180);
  lastPointer = { phase, selector: css.slice(0, 120), label: text?.slice(0, 120) ?? null, status: 'evaluation-pending' };
  const measured = await evaluate(`(() => {
    const matches = [...document.querySelectorAll(${json(css)})].filter(e =>
      ${text ? `(e.getAttribute('aria-label') || e.textContent.trim()) === ${json(text)}` : 'true'});
    const target = matches.find(e => e.getClientRects().length);
    const e = target || matches[0];
    ${mobile ? "if (target && !target.disabled) target.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'});" : ''}
    const base = {found:!!e,renderedTarget:!!target,disabled:e ? !!e.disabled : null,
      viewport:{width:innerWidth,height:innerHeight},scroll:{x:scrollX,y:scrollY},
      rect:null,visibility:null,opacity:null,display:null,pointerEvents:null,hit:null,point:null};
    if (!e) return base;
    const r=e.getBoundingClientRect(),s=getComputedStyle(e),x=r.x+r.width/2,y=r.y+r.height/2;
    let opacity=1,displayed=true;
    for(let a=e;a;a=a.parentElement){const style=getComputedStyle(a);opacity*=Number(style.opacity);if(style.display==='none')displayed=false;}
    const hit=document.elementFromPoint(x,y);
    const metadata = node => node ? {tag:node.tagName.toLowerCase(),
      role:(node.getAttribute('role') || '').slice(0,64),testId:(node.getAttribute('data-testid') || '').slice(0,64)} : null;
    const visible=displayed && s.visibility==='visible' && opacity>0 && r.width>0 && r.height>0;
    const hittable=!!target && !e.disabled && visible && x>=0 && x<innerWidth && y>=0 && y<innerHeight && (hit===e || e.contains(hit));
    return {...base,rect:{x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom},
      visibility:{computed:s.visibility,displayed,effective:visible},opacity,display:s.display,
      pointerEvents:s.pointerEvents,hit:metadata(hit),point:hittable?{x,y}:null};
  })()`);
  lastPointer = { ...lastPointer, status: 'measured', ...measured };
  await record('pointer-attempt', lastPointer);
  const point = measured.point;
  requireCheck(point);
  await send('Input.dispatchMouseEvent', { type: 'mouseMoved', ...point });
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', button: 'left', buttons: 1, clickCount: 1, ...point });
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', button: 'left', buttons: 0, clickCount: 1, ...point });
}
const button = text => click('button', text);
async function key(key, code, modifiers = 0) {
  phase = `keyboard-${key}`;
  // CDP needs the character payload to perform Enter's native text-editing action.
  const character = key === 'Enter' && (modifiers === 0 || modifiers === 8) ? { text: '\r', unmodifiedText: '\r' } : {};
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key, code, modifiers, windowsVirtualKeyCode: key === 'a' ? 65 : key === 'Escape' ? 27 : 13, ...character });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key, code, modifiers });
}
async function fill(value) {
  await click('#raw-history');
  await key('a', 'KeyA', 2);
  await send('Input.insertText', { text: value });
  requireCheck(await evaluate(`document.querySelector('#raw-history').value === ${json(value)}`));
}
async function integrity(name) {
  phase = name;
  const state = await evaluate(`({csp:window.__rawFixture.csp,storage:localStorage.length+sessionStorage.length,
    cookies:document.cookie.length,styles:document.querySelectorAll('style').length,
    workspace:document.querySelector('[data-workspace]')?.dataset.workspace,
    activeMode:document.querySelector('[role=tab][data-state=active]')?.textContent.trim()})`);
  await record(name, { ...state, external: external.length, runtimeErrors: runtimeErrors.length,
    runtimeErrorCategories: [...runtimeErrors], fixturePosts: posts.length });
  requireCheck(state.csp.length === 0 && state.storage === 0 && state.cookies === 0 && state.styles === 0);
  // The closed mobile Sheet unmounts its tabs; the workspace still identifies the active view.
  requireCheck(state.workspace === 'raw' && (mobile || state.activeMode === 'Responder conversación')
    && !external.length && !runtimeErrors.length);
}
async function geometry(name, { long = false, expanded = true } = {}) {
  phase = name;
  await evaluate(`Promise.all(document.getAnimations().filter(a => a.effect?.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})))`);
  const data = await evaluate(`(() => {
    const measure = css => {
      const e = document.querySelector(css); if (!e) return null;
      const r = e.getBoundingClientRect(), s = getComputedStyle(e);
      let opacity=1; for(let a=e;a;a=a.parentElement) opacity*=Number(getComputedStyle(a).opacity);
      const hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);
      return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height,
        clientHeight:e.clientHeight,scrollHeight:e.scrollHeight,scrollTop:e.scrollTop,
        overflowY:s.overflowY,overflowX:s.overflowX,opacity,disabled:!!e.disabled,
        padding:[s.paddingTop,s.paddingRight,s.paddingBottom,s.paddingLeft].map(parseFloat),
        color:s.color,background:s.backgroundColor,hit:hit===e||e.contains(hit)};
    };
    return {viewport:{width:innerWidth,height:innerHeight},document:{width:document.documentElement.scrollWidth,
      height:document.documentElement.scrollHeight,top:scrollY,left:scrollX,bodyOverflow:getComputedStyle(document.body).overflowY},
      state:document.querySelector('.raw-composer').dataset.state,
      heading:measure('.conversation-start'),column:measure('.raw-composer'),library:measure('.library-body'),
      sidebar:measure('[data-slot=sidebar-gap]'),page:measure('.workspace-page'),
      left:measure('.raw-input-panel'),right:measure('.raw-draft-panel'),input:measure('#raw-history'),
      disclosure:measure('#raw-disclosure'),submitted:measure('.raw-submitted-text'),draft:measure('.raw-draft-scroll'),
      leftFooter:measure('.raw-input-panel .raw-action-footer'),rightFooter:measure('.raw-copy-footer'),
      generate:measure('.raw-input-panel button.primary'),clear:measure('.raw-input-panel button[data-variant=ghost]'),
      copy:measure('.raw-copy-footer button'),alert:measure('.raw-draft-panel [role=alert]'),label:measure('#raw-fixture-label')};
  })()`);
  await record(name, data); // Measurements survive even if the following assertion fails.
  requireCheck(data.document.width <= viewport.width + 1);
  requireCheck(data.input.opacity === 1 && data.disclosure.opacity === 1 && !data.input.disabled);
  requireCheck(data.label && data.label.height > 0);
  const inside = (child, parent) => child && child.x >= parent.x - 1 && child.right <= parent.right + 1 && child.y >= parent.y - 1 && child.bottom <= parent.bottom + 1;
  requireCheck(inside(data.leftFooter, data.left));
  requireCheck(data.disclosure.height > 0 && data.disclosure.y >= data.left.bottom
    && data.disclosure.y - data.generate.bottom <= 36);
  if (!mobile) {
    requireCheck(data.left.height >= 120 && data.left.height <= 170);
    requireCheck(inside(data.disclosure, {x:0,y:0,right:viewport.width,bottom:viewport.height}));
  }
  requireCheck(data.left.width <= 780 && Math.abs(data.left.width-data.column.width) <= 1);
  requireCheck(data.state === 'start' ? !data.right && !!data.heading : !!data.right && !data.heading);
  if (data.right) {
    requireCheck(inside(data.rightFooter, data.right));
    requireCheck(data.right.bottom <= data.left.y && Math.abs(data.right.x-data.left.x) <= 1
      && Math.abs(data.right.width-data.left.width) <= 1);
  }
  if (!mobile) {
    requireCheck(data.document.top === 0 && data.document.left === 0 && data.document.height <= viewport.height + 1);
    if (expanded) requireCheck(data.sidebar.width >= 232 && data.sidebar.width <= 248);
    requireCheck(data.page.padding[1] >= 24 && data.page.padding[3] >= 24);
    requireCheck(Math.abs((data.left.x+data.left.right)/2-(data.page.x+data.page.right)/2) <= 1);
    if (data.heading) requireCheck(data.heading.bottom < data.left.y && data.left.y > data.page.y + 60);
    for (const panel of [data.left, data.right].filter(Boolean)) requireCheck(inside(panel, {x:0,y:0,right:viewport.width,bottom:viewport.height}));
    if (data.alert) requireCheck(inside(data.alert, data.right) && data.alert.hit);
        // Disabled buttons intentionally opt out of pointer hits; their bounds must still be visible.
        for (const control of [data.generate, data.clear, data.copy].filter(Boolean)) requireCheck(
          control.width > 0 && control.height > 0 && control.opacity > 0
          && inside(control, {x:0,y:0,right:viewport.width,bottom:viewport.height})
          && (control.disabled || control.hit || (data.library
            && control.x+control.width/2 >= data.library.x && control.x+control.width/2 <= data.library.right
            && control.y+control.height/2 >= data.library.y && control.y+control.height/2 <= data.library.bottom)));
  } else {
    requireCheck(data.input.height <= 260 && (!data.draft || data.draft.height <= 420) && data.document.height < 3000);
  }
  if (long) {
    for (const body of [data.submitted, data.draft]) requireCheck(body.scrollHeight > body.clientHeight + 1 && ['auto','scroll'].includes(body.overflowY));
  }
  return data;
}
async function settleCapture(name) {
  phase = `paint-${name}`;
  const settled = await evaluate(`(async () => {
    let timer;
    const sample = () => {
      const r=document.querySelector('.raw-copy-footer')?.getBoundingClientRect();
      return [innerWidth,innerHeight,scrollY,document.documentElement.scrollHeight,r?.y,r?.height];
    };
    try {
      return await Promise.race([
        (async () => {
          await document.fonts.ready;
          await Promise.all(document.getAnimations().filter(a => a.effect?.getTiming().iterations !== Infinity).map(a => a.finished.catch(() => {})));
          await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
          const before=sample();
          await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
          const after=sample();
          return {fontsReady:document.fonts.status==='loaded',layoutStable:JSON.stringify(before)===JSON.stringify(after),before,after};
        })(),
        new Promise(resolve=>{timer=setTimeout(()=>resolve({timedOut:true}),2200);})
      ]);
    } finally {clearTimeout(timer);}
  })()`);
  await record(`paint-${name}`, settled);
  requireCheck(settled.fontsReady && settled.layoutStable);
}
async function mobileBottomDetail(name) {
  if (!mobile) return;
  phase=`detail-${name}`;
  try {
    await evaluate('window.scrollTo(0,document.documentElement.scrollHeight)');
    await settleCapture(`${name}-bottom`);
    phase=`detail-${name}-capture`;
    const measured=await evaluate(`(() => {
      const rect=css=>{const r=document.querySelector(css).getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom};};
      return {viewport:{width:innerWidth,height:innerHeight},scroll:{x:scrollX,y:scrollY},
        documentHeight:document.documentElement.scrollHeight,footer:rect('.raw-input-panel .raw-action-footer'),disclosure:rect('#raw-disclosure')};
    })()`);
    const image=Buffer.from((await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false})).data,'base64');
    const file=`${name}-bottom-detail.png`,png={width:image.readUInt32BE(16),height:image.readUInt32BE(20)};
    await writeFile(join(out,file),image,{flag:'wx'});
    const entry={category:'mobile-bottom-detail',file,png,...measured,fullPage:false,
      labelPlacement:'companion HTML and gallery caption outside unmodified viewport image',wrapper:`${name}-bottom-detail.html`};
    details.push(entry);
    await artifact(entry.wrapper,`<!doctype html><meta charset="utf-8"><title>Fixture bottom detail</title><h1>${label}</h1><p>Supplementary real viewport capture, not a canonical matrix image. Label is outside captured UI; pixels are unmodified. Viewport ${measured.viewport.width}×${measured.viewport.height}; PNG ${png.width}×${png.height}.</p><img src="${file}" alt="Fictional mobile bottom detail">`);
    await record(`detail-${name}`,entry);
    requireCheck(png.width===viewport.width && png.height===viewport.height);
    requireCheck(measured.footer.y>=0 && measured.footer.bottom<=viewport.height+1);
    requireCheck(measured.disclosure.y>=measured.footer.bottom && measured.disclosure.bottom<=viewport.height+1
      && measured.disclosure.y-measured.footer.bottom<=36);
  } finally {
    await evaluate('window.scrollTo(0,0)');
    await settleCapture(`${name}-restored-top`);
    requireCheck(await evaluate('scrollY===0'));
  }
}
async function screenshot(name) {
  await settleCapture(name);
  phase = `capture-${name}`;
  const dimensions = await evaluate('({width:innerWidth,height:document.documentElement.scrollHeight,top:scrollY})');
  if (!mobile) requireCheck(dimensions.top === 0);
  const args = mobile ? { captureBeyondViewport: true, clip: { x:0,y:0,width:viewport.width,height:dimensions.height,scale:1 } } : { captureBeyondViewport: false };
  const image = Buffer.from((await send('Page.captureScreenshot', { format:'png', ...args })).data, 'base64');
  const png = { width:image.readUInt32BE(16),height:image.readUInt32BE(20) };
  await writeFile(join(out, `${name}.png`), image, {flag:'wx'});
  captures.push({file:`${name}.png`,viewport:{...viewport},png,fullPage:mobile});
  await record(`capture-${name}`, captures.at(-1));
  requireCheck(png.width === viewport.width && png.height === (mobile ? dimensions.height : viewport.height));
  await mobileBottomDetail(name);
}
async function internalScroll(name, css) {
  phase = name;
  const before = await geometry(`${name}-before`, {long:true});
  const end = await evaluate(`(() => {const e=document.querySelector(${json(css)});e.scrollTop=e.scrollHeight;
    return {top:e.scrollTop,height:e.clientHeight,total:e.scrollHeight,page:scrollY};})()`);
  requireCheck(end.top > 0 && Math.abs(end.top+end.height-end.total)<=1 && end.page === before.document.top);
  if (css === '.raw-draft-scroll') requireCheck(await evaluate(`(() => {
    const e=document.querySelector('.raw-draft-scroll'), last=e.querySelector('.static-markdown').lastElementChild;
    const a=e.getBoundingClientRect(), b=last.getBoundingClientRect();return b.bottom<=a.bottom+1 && b.bottom>a.top;
  })()`));
  const after = await geometry(`${name}-end`, {long:true});
  for (const which of ['leftFooter','rightFooter']) requireCheck(Math.abs(before[which].y-after[which].y)<=1 && Math.abs(before[which].height-after[which].height)<=1);
  await evaluate(`document.querySelector(${json(css)}).scrollTop=0`);
  requireCheck(await evaluate(`document.querySelector(${json(css)}).scrollTop===0`));
}
function plan(kind, expectedHistory = history, text = draft) {
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const item = { kind, expectedHistory, text, gate, release, received:false, finished:false };
  plans.push(item); return item;
}
async function generate(kind, expectedHistory = history, text = draft, viaEnter = false) {
  const item = plan(kind, expectedHistory, text), before = posts.length;
  const baseline={server:before,client:await fetchCount(),interceptions:interceptions.length};
  const intercepted=kind==='transport' && mode==='matrix';
  if (viaEnter) { await click('#raw-history'); await key('Enter', 'Enter'); }
  else await button('Generar borrador');
  await wait(() => item.received, 'fixture-request-received');
  requireCheck(posts.length === before+(intercepted?0:1));
  await wait(() => evaluate(`document.querySelector('.raw-draft-panel [role=status]').textContent.includes('Preparando el próximo DM…')`), 'pending-fixture-status');
  requireCheck(await evaluate(`document.querySelector('.raw-input-panel button.primary').disabled && !document.querySelector('.raw-copy-footer button')`));
  await geometry(`pending-${posts.length}`);
  if (kind === 'dm' && expectedHistory === history && text === draft) {
    const loader = await evaluate(`(() => {const e=document.querySelector('.generation-mark');const r=e.getBoundingClientRect();return {height:r.height,animated:e.querySelector('i').getAnimations().length>0,emptyRegion:!!document.querySelector('.raw-draft-scroll')};})()`);
    requireCheck(loader.height > 0 && loader.animated && !loader.emptyRegion);
    await record('honest-loader', loader);
    await screenshot(`${viewport.width}x${viewport.height}-loading`);
  }
  item.release();
  await wait(() => item.finished, 'fixture-response-released');
  await wait(() => evaluate(`document.querySelector('.raw-composer').getAttribute('aria-busy')==='false'`), 'fixture-settled');
  const delta=await requestDelta(`request-delta-${kind}-${before+1}`,baseline);
  requireCheck(delta.serverRequestDelta===(intercepted?0:1) && delta.clientFetchDelta===1 && delta.interceptionDelta===(intercepted?1:0));
  return item;
}
async function serve(req, res) {
  for (const [name,value] of Object.entries({'Content-Security-Policy':CSP,'Cache-Control':'no-store','Referrer-Policy':'no-referrer','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY'})) res.setHeader(name,value);
  const respond = (value, code=200) => {res.writeHead(code,{'Content-Type':'application/json'});res.end(json(value));};
  const path = req.url;
  // Count before Host validation and plan lookup: rejected deliveries are attempts too.
  const attempt=req.method==='POST' ? {sequence:posts.length+1,method:'POST',
    path:['/api/raw-draft','/api/auth/login','/api/auth/logout'].includes(path)?path:'other',phase,planKind:'unplanned',expectedBodyMatch:null} : null;
  if(attempt)posts.push(attempt);
  if (req.headers.host !== parseURL(origin).host) {if(attempt)runtimeIssue('forbidden-fixture-host');return respond({},403);}
  if (req.method === 'POST') {
    if (path === '/api/auth/login' || path === '/api/auth/logout') {
      const item = authPlans.shift();
      if (!item || item.path !== path) { runtimeIssue('unplanned-auth-post'); return respond({}, 403); }
      const chunks = []; let bytes = 0;
      for await (const chunk of req) { bytes += chunk.length; if (bytes > 8192) return respond({}, 413); chunks.push(chunk); }
      const body = parseJSON(Buffer.concat(chunks).toString());
      const valid = req.headers.origin === origin && req.headers['x-csrf-token'] === token
        && json(body) === json(item.body);
      attempt.planKind = 'auth-fixture'; attempt.expectedBodyMatch = valid;
      requireCheck(valid);
      libraryConnected = path === '/api/auth/login'; persistenceActivated = true;
      return respond({connected:libraryConnected,empty:false,count:libraryConnected?2:0,revision:2});
    }
    if (path !== '/api/raw-draft') { runtimeIssue('forbidden-fixture-post'); return respond({},403); }
    const item = plans.shift();
    if(item)attempt.planKind=item.kind;
    if (!item) { runtimeIssue('unplanned-fixture-post'); return respond({},409); }
    const chunks=[];let bytes=0;
    for await(const chunk of req) {bytes+=chunk.length;if(bytes>200000)return respond({},413);chunks.push(chunk);}
    const body=parseJSON(Buffer.concat(chunks).toString());
    const valid = req.headers['x-csrf-token']===token && req.headers.origin===origin &&
      Object.keys(body).sort().join(',')==='consent,history' && body.consent===true && body.history===item.expectedHistory;
    attempt.expectedBodyMatch=valid;
    requireCheck(valid);item.received=true;
    await item.gate;
    if (stopped) return;
    if(item.kind==='transport') req.socket.destroy();
    else if(item.kind==='error') respond({error:'Fallo ficticio'},502);
    else if(item.kind==='malformed') respond({result:{type:'dm',text:'Inválido ficticio'}});
    else if(item.kind==='needs_context') respond({result:{type:'needs_context',question:'Qué parte falta en este ejemplo ficticio?'},retrieval:{status:'off',count:0},revision:1});
    else respond(envelope(item.text));
    item.finished=true;return;
  }
  if(req.method!=='GET')return respond({},405);
  if(path==='/api/bootstrap') {token=`fixture-only-${++bootCount}`;return respond({app:'tato-local',protocol:1,csrf_token:token,model:'unknown',effort:'unknown'});}
  if(path==='/api/auth/status')return respond({connected:libraryConnected,empty:false,count:libraryConnected?2:0,revision:1});
  if(path==='/api/auth/persistence')return persistenceActivated
    ? respond({enabled:true,remembered:libraryConnected,problem:false}) : respond({},404);
  if(path==='/favicon.ico'){res.writeHead(204);return res.end();}
  if(path==='/assets/raw-fixture-label.css') {
    res.writeHead(200,{'Content-Type':'text/css'});
    return res.end('#raw-fixture-label{display:block;font:10px/14px system-ui;color:#ffe8ad;margin-top:2px}');
  }
  if(path==='/' || /^\/assets\/[A-Za-z0-9_-]+\.(js|css)$/.test(path)) {
    const file=join(root,'dist',path==='/'?'index.html':path.slice(1));
    requireCheck(resolve(await realpath(file))===resolve(file));
    let body=await readFile(file);
    if(path==='/') body=Buffer.from(body.toString().replace('</head>','<link rel="stylesheet" href="/assets/raw-fixture-label.css"></head>'));
    res.writeHead(200,{'Content-Type':path==='/'?'text/html':path.endsWith('.js')?'text/javascript':'text/css'});return res.end(body);
  }
  runtimeIssue('forbidden-fixture-get');respond({},404);
}
async function reload() {
  const before=posts.length;
  await send('Page.reload');
  await wait(() => evaluate(`!!document.querySelector('#raw-fixture-label') && !!document.querySelector('#raw-history') && document.body.textContent.includes('Servidor local conectado')`),'mounted-raw');
  requireCheck(posts.length===before && await evaluate(`document.querySelector('#raw-history').value===''`));
}
async function extras() {
  phase='extra-functional-checks';
  interactionStep='extras-enter-reload';
  await reload();const before=posts.length;
  interactionStep='extras-enter-fill';
  await fill('Demostración ficticia');await key('Enter','Enter',8);
  requireCheck(await evaluate(`document.querySelector('#raw-history').value==='Demostración ficticia\\n'`));
  requireCheck(posts.length===before);
  await generate('dm','Demostración ficticia\n','Salida ficticia por Enter',true);
  requireCheck(posts.length===before+1);
  interactionStep='extras-hostile-reload';await reload();
  interactionStep='extras-hostile-fill';await fill(history);
  interactionStep='extras-hostile-generate';await generate('dm',history,hostile);
  requireCheck(await evaluate(`document.querySelectorAll('.static-markdown img,.static-markdown iframe,.static-markdown a[href],.static-markdown script').length===0 && document.querySelector('.static-markdown').textContent.includes('<img src=')`));
  interactionStep='extras-copy-success';await button('Copiar DM');
  await wait(() => evaluate(`document.querySelector('.raw-draft-panel [role=status]').textContent==='DM copiado. No se envió.'`),'copy-success');
  requireCheck(await evaluate(`window.__rawFixture.copied===${json(hostile)}`));
  interactionStep='extras-copy-failure';await evaluate('window.__rawFixture.copyFails=true');await button('Copiar DM');
  await wait(() => evaluate(`document.querySelector('[role=alert]')?.textContent==='No se pudo copiar el DM.'`),'copy-failure');
  await evaluate('window.__rawFixture.copyFails=false');
  interactionStep='extras-needs-context-fill';await fill(history);
  interactionStep='extras-needs-context-generate';await generate('needs_context');
  phase='extras-needs-context-contract';
  requireCheck(await evaluate(`!document.querySelector('.raw-copy-footer button') && document.querySelector('.raw-draft-panel [role=status]').textContent==='Falta contexto. No se generó un DM.'`));
  phase='extras-input-reference-before';
  await record('extras-input-reference-before',{operation:'store-page-local-node'});
  const stored=await evaluate(`(() => {window.__rawFixture.input=document.querySelector('#raw-history');return Boolean(window.__rawFixture.input);})()`);
  phase='extras-input-reference-after';
  await record('extras-input-reference-after',{stored});
  requireCheck(stored);
  const same = async () => requireCheck(await evaluate(`window.__rawFixture.input===document.querySelector('#raw-history') && document.querySelector('#raw-history').value==='' && document.querySelector('.raw-submitted-text')?.textContent===${json(history)}`));
  interactionStep='extras-library';await click('summary','Biblioteca');
  await wait(() => evaluate(`!!document.querySelector('.library-body') && document.body.textContent.includes('2 criterios disponibles')`),'fictional-library');
  requireCheck(await evaluate(`!document.querySelector('#editorial-email') && document.querySelector('.persistence-state').textContent.includes('Persistencia no activada')`));
  for(const text of ['Criterios y fuentes','Privacidad y límites']) {
    interactionStep='extras-disclosure-open';await click('summary',text);await same();await geometry(`expanded-${text==='Criterios y fuentes'?'criteria':text==='Privacidad y límites'?'privacy':'diagnostics'}`);
    if(text==='Privacidad y límites') {
      const support=await evaluate(`(() => {const e=document.querySelector('.library-body');e.scrollTop=e.scrollHeight;return {height:e.clientHeight,total:e.scrollHeight,top:e.scrollTop,page:scrollY,overflow:getComputedStyle(e).overflowY};})()`);
      await record('support-scroll-ownership',support);
      requireCheck(support.total>support.height && support.top>0 && support.page===0 && support.overflow==='auto');
      await evaluate(`document.querySelector('.library-body').scrollTop=0`);
    }
    interactionStep='extras-disclosure-close';await click('summary',text);
  }
  await same();await geometry('library-open');
  authPlans.push({path:'/api/auth/logout',body:{}});
  await button('Desconectar');
  await wait(() => evaluate(`document.querySelector('.library-body [role=status]').textContent==='Biblioteca desconectada.'`),'fictional-logout');
  const fillCredential = async (id, value) => { await click(id); await send('Input.insertText',{text:value}); };
  await fillCredential('#editorial-email','fictional@example.invalid');
  await fillCredential('#editorial-password','fictional-unused-password');
  authPlans.push({path:'/api/auth/login',body:{email:'fictional@example.invalid',password:'fictional-unused-password'}});
  await button('Conectar');
  await wait(() => evaluate(`document.querySelector('.persistence-state').textContent.includes('Sesión recordada')`),'fictional-remembered');
  requireCheck(await evaluate(`!document.querySelector('#editorial-email') && !document.querySelector('.raw-copy-footer button')`));
  await button('Cerrar biblioteca');await same();await geometry('library-closed');
  await click('summary','Detalles técnicos');await same();await click('summary','Detalles técnicos');
  interactionStep='extras-sidebar-collapse';await button('Alternar navegación');await same();await geometry('sidebar-collapsed',{expanded:false});
  interactionStep='extras-sidebar-expand';await button('Alternar navegación');await same();await geometry('sidebar-expanded');
  for(const kind of ['malformed','error','transport']) {
    const baseline={server:posts.length,client:await fetchCount(),interceptions:interceptions.length};
    const nonceBefore=token;
    interactionStep=`extras-rejection-${kind}`;await fill(history);await generate(kind);const count=posts.length;
    await wait(() => evaluate(`!!document.querySelector('[role=alert]') && !document.querySelector('.raw-copy-footer button')`),`rejected-${kind}`);
    if(kind==='transport') await wait(()=>evaluate(`document.querySelector('.connection-state')?.textContent==='Sin conexión local' && document.querySelector('.raw-input-panel button.primary').disabled`),'transport-ui-disconnected');
    await delay(180);
    await requestDelta(`negative-settlement-${kind}`,baseline);
    requireCheck(posts.length===count);await same();
    interactionStep=`extras-reconnect-${kind}`;await button('Reconectar');
    await wait(() => evaluate(`document.body.textContent.includes('Servidor local conectado') && !document.querySelector('.raw-input-panel button.primary').disabled`),`reconnect-${kind}`);
    const delta=await requestDelta(`negative-reconnect-${kind}`,baseline);
    requireCheck(posts.length===count && delta.serverRequestDelta===(kind==='transport'?0:1)
      && delta.clientFetchDelta===1 && delta.interceptionDelta===(kind==='transport'?1:0) && token!==nonceBefore);await same();
  }
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  requireCheck(await evaluate(`document.getAnimations().length===0`));
  await record('reduced-motion',{animations:0});
  await integrity('extra-contracts');
}
async function matrix() {
  for(const [width,height] of [[1366,768],[1920,1080],[390,844]]) {
    viewport={width,height};mobile=width===390;
    await send('Emulation.setDeviceMetricsOverride',{width,height,deviceScaleFactor:1,mobile});
    await reload();const prefix=`${width}x${height}`;
    requireCheck(await evaluate(`!document.querySelector('.raw-draft-panel') && document.querySelector('.conversation-start h2').textContent==='Qué conversación preparamos?'`));
    await geometry(`${prefix}-empty`);await screenshot(`${prefix}-empty`);await integrity(`${prefix}-empty-integrity`);
    await fill(history);await generate('dm');
    requireCheck(await evaluate(`(() => {
      const region=document.querySelector('.raw-draft-scroll'), first=document.querySelector('.static-markdown').firstElementChild;
      const a=region.getBoundingClientRect(),b=first.getBoundingClientRect();
      return region.scrollTop===0 && first.textContent==='INICIO DEL BORRADOR FICTICIO' && b.top>=a.top && b.bottom<=a.bottom;
    })()`));
    await internalScroll(`${prefix}-history-scroll`,'.raw-submitted-text');
    await internalScroll(`${prefix}-draft-scroll`,'.raw-draft-scroll');
    // Only mobile uses normal document scrolling; desktop never scrolls to conceal overflow.
    if(mobile) {
      await button('Copiar DM');requireCheck(await evaluate(`window.__rawFixture.copied===${json(draft)}`));
      await evaluate('window.scrollTo(0,0)');
    }
    await geometry(`${prefix}-long`,{long:true});await screenshot(`${prefix}-long`);await integrity(`${prefix}-long-integrity`);
    await fill(history);await generate('error');
    requireCheck(await evaluate(`document.querySelector('#raw-history').value==='' && document.querySelector('.raw-submitted-text')?.textContent===${json(history)} && !!document.querySelector('[role=alert]') && !document.querySelector('.raw-copy-footer button')`));
    if(mobile)await evaluate('window.scrollTo(0,0)');
    await geometry(`${prefix}-error`);await screenshot(`${prefix}-error`);await integrity(`${prefix}-error-integrity`);
  }
  viewport={width:1366,height:768};mobile=false;
  await send('Emulation.setDeviceMetricsOverride',{...viewport,deviceScaleFactor:1,mobile:false});
  await extras();
}
async function cleanup() {
  if(stopped)return;stopped=true;
  if(socket?.readyState===WebSocket.OPEN){try{await send('Browser.close');}catch{}socket.close();}
  if(browser && browser.exitCode===null)browser.kill(); // Only our child handle, never a PID lookup.
  for(const p of pending.values()){clearTimeout(p.timer);p.reject(new Error('Fixture closed'));}pending.clear();
  server?.closeAllConnections();
  if(server?.listening)await new Promise(resolve=>server.close(resolve));
  // No deletion. Own profile, screenshots and metadata remain in the fresh temporary directory.
}
async function diagnoseTransport() {
  viewport={width:1366,height:768};mobile=false;
  await send('Emulation.setDeviceMetricsOverride',{...viewport,deviceScaleFactor:1,mobile:false});
  await reload();
  interactionStep='diagnose-transport-fill';
  const text='Demostración ficticia de transporte, sin datos reales.';
  await fill(text);
  const baseline={server:posts.length,client:await fetchCount()};
  requireCheck(baseline.server===0 && baseline.client===0);
  const item=plan('transport',text);
  interactionStep='diagnose-transport-single-action';await button('Generar borrador');
  await wait(()=>item.received,'diagnose-transport-received');
  item.release();
  // Observe a bounded window even when an unexpected second delivery occurs.
  await wait(()=>item.finished,'diagnose-transport-socket-destroyed');
  phase='diagnose-transport-observation-window';await delay(1500);
  const delta=await requestDelta('diagnose-transport-deltas',baseline);
  const ui=await evaluate(`({connected:document.querySelector('.connection-state')?.textContent==='Servidor local conectado',
    alertPresent:!!document.querySelector('[role=alert]'),busy:document.querySelector('.raw-composer')?.getAttribute('aria-busy'),
    copyPresent:!!document.querySelector('.raw-copy-footer button'),generateDisabled:!!document.querySelector('.raw-input-panel button.primary')?.disabled})`);
  await record('diagnose-transport-observed',{mode,windowMs:1500,...delta,ui,attempts:posts,categories:runtimeErrors});
  phase='diagnose-transport-strict-accounting';
  requireCheck(delta.clientFetchDelta===1 && delta.serverRequestDelta===1 && ui.busy==='false');
  await integrity('diagnose-transport-integrity');
}
async function handlePaused({request,requestId}) {
  const local=request.url.startsWith(`${origin}/`);
  if(!local) {
    external.push('blocked-external');
    return send('Fetch.failRequest',{requestId,errorReason:'BlockedByClient'});
  }
  // The diagnostic deliberately retains real HTTP socket destruction and delivery accounting.
  if(mode==='matrix' && request.method==='POST' && request.url===`${origin}/api/raw-draft`) {
    const item=plans[0];
    if(!item || item.kind==='transport') {
      const entry={sequence:interceptions.length+1,method:'POST',path:'/api/raw-draft',phase,
        planKind:item?.kind ?? 'unplanned',expectedBodyMatch:null,released:false};
      interceptions.push(entry);
      if(!item) {
        runtimeIssue('unplanned-fixture-interception');
        return send('Fetch.failRequest',{requestId,errorReason:'BlockedByClient'});
      }
      plans.shift();
      let valid=false;
      try {
        const body=parseJSON(request.postData);
        const headers=Object.fromEntries(Object.entries(request.headers).map(([key,value])=>[key.toLowerCase(),value]));
        valid=headers['x-csrf-token']===token && headers.origin===origin &&
          Object.keys(body).sort().join(',')==='consent,history' && body.consent===true && body.history===item.expectedHistory;
      } catch { /* No payload or headers enter diagnostics. */ }
      entry.expectedBodyMatch=valid;
      if(!valid) {
        runtimeIssue('invalid-transport-interception');
        return send('Fetch.failRequest',{requestId,errorReason:'BlockedByClient'});
      }
      item.received=true;
      await item.gate;
      if(stopped)return;
      await send('Fetch.failRequest',{requestId,errorReason:'Failed'});
      entry.released=true;item.finished=true;return;
    }
  }
  return send('Fetch.continueRequest',{requestId});
}
async function run() {
  requireCheck(mode!=='invalid');
  await access(chromePath);await access(join(root,'dist/index.html'));
  out=await mkdtemp(join(tmpdir(),'tato-raw-fixture-'));const profile=join(out,'chrome-profile');await mkdir(profile);
  server=createServer((req,res)=>{serve(req,res).catch(()=>{runtimeIssue('fixture-response-error');if(!res.headersSent)res.writeHead(500);res.end();});});
  await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',resolve);});
  requireCheck(server.address().port!==8765);origin=`http://127.0.0.1:${server.address().port}`;
  browser=spawn(chromePath,['--headless=new','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1',`--user-data-dir=${profile}`,'--no-first-run','--no-default-browser-check','--disable-extensions','--disable-background-networking','--disable-component-update','--disable-sync','--disable-default-apps','--disable-domain-reliability','--metrics-recording-only','--no-proxy-server','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1','about:blank'],{stdio:['ignore','ignore','pipe']});
  let endpoint='',spawnFailed=false;
  browser.on('error',()=>{spawnFailed=true;});browser.stderr.on('data',chunk=>{endpoint=(endpoint+chunk.toString()).slice(-16000);});
  await wait(()=>{requireCheck(!spawnFailed);return /DevTools listening on (ws:\/\/127\.0\.0\.1:\d+\/[^\s]+)/.test(endpoint);},'chrome-endpoint');
  const ws=endpoint.match(/DevTools listening on (ws:\/\/127\.0\.0\.1:\d+\/[^\s]+)/)[1];
  const debug=parseURL(ws);requireCheck(debug.hostname==='127.0.0.1' && debug.port!=='8765');
  const targets=await(await fetch(`http://${debug.host}/json/list`,{signal:AbortSignal.timeout(6500),redirect:'error'})).json();
  const target=targets.find(t=>t.type==='page' && t.url==='about:blank');requireCheck(target);
  const pageURL=parseURL(target.webSocketDebuggerUrl);requireCheck(pageURL.protocol==='ws:' && pageURL.host===debug.host);
  socket=new WebSocket(pageURL);
  socket.addEventListener('message',event=>{
    let message;try{message=JSON.parse(event.data);}catch{runtimeIssue('invalid-cdp-message');return;}
    if(message.id){const p=pending.get(message.id);if(!p)return;clearTimeout(p.timer);pending.delete(message.id);if(message.error)p.reject(new Error('CDP rejected'));else p.resolve(message.result);}
    else if(message.method==='Fetch.requestPaused'){
      handlePaused(message.params).catch(()=>runtimeIssue('interception-error'));
    }else if(message.method==='Runtime.exceptionThrown')runtimeIssue('runtime-exception');
    else if(message.method==='Runtime.consoleAPICalled' && message.params.type==='error')runtimeIssue('console-error');
  });
  await wait(()=>socket.readyState===WebSocket.OPEN,'cdp-open');
  await send('Page.enable');await send('Runtime.enable');await send('Fetch.enable',{patterns:[{urlPattern:'*'}]});
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'no-preference'}]});
  await send('Page.addScriptToEvaluateOnNewDocument',{source:`
    window.__rawFixture={csp:[],copied:null,copyFails:false,rawFetchCount:0};
    const nativeFetch=window.fetch;
    window.fetch=function(...args){
      // Observe without awaiting, replacing the Promise, coercing arguments or retrying.
      const input=args[0];
      const url=typeof input==='string'?input:input instanceof Request?input.url:input instanceof URL?input.href:null;
      if(url==='/api/raw-draft' || url===location.origin+'/api/raw-draft')window.__rawFixture.rawFetchCount++;
      return Reflect.apply(nativeFetch,this,args);
    };
    document.addEventListener('securitypolicyviolation',e=>window.__rawFixture.csp.push(e.violatedDirective));
    Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{
      if(window.__rawFixture.copyFails)throw new Error('Fixture clipboard failure');window.__rawFixture.copied=text;
    }}});
    new MutationObserver(()=>{const title=document.querySelector('.header-title');if(title && !document.querySelector('#raw-fixture-label')){
      const label=document.createElement('small');label.id='raw-fixture-label';label.textContent=${json(label)};title.append(label);
    }}).observe(document,{childList:true,subtree:true});
  `});
  await send('Page.navigate',{url:origin});
  if(mode==='diagnose-transport')await diagnoseTransport();else await matrix();
  requireCheck((mode==='diagnose-transport' ? captures.length===0 : captures.length===12)
    && plans.length===0 && authPlans.length===0 && posts.every(p=>p.planKind!=='unplanned' && p.expectedBodyMatch===true)
    && interceptions.every(p=>p.planKind==='transport' && p.expectedBodyMatch===true && p.released) && !runtimeErrors.length);
}
async function captureFailureDiagnostic(originalPhase) {
  // Separate from the nine required states; never scroll or modify the failing page.
  const budget = Math.min(2500, deadline - Date.now());
  failureDiagnostic = { category:'diagnostic', status:'unavailable', originalPhase };
  if (!out || !socket || socket.readyState !== WebSocket.OPEN || budget <= 0) {
    failureDiagnostic.status='skipped-no-session-or-budget';return;
  }
  try {
    const result=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false},budget);
    const image=Buffer.from(result.data,'base64');
    const png={width:image.readUInt32BE(16),height:image.readUInt32BE(20)};
    await writeFile(join(out,'failure-diagnostic.png'),image,{flag:'wx'});
    failureDiagnostic={category:'diagnostic',status:'captured',originalPhase,file:'failure-diagnostic.png',png,
      requestedViewport:viewport ? {...viewport} : null,fullPage:false};
  } catch {
    // Deliberately omit exception messages, remote payloads and page content.
    failureDiagnostic.status='capture-failed';
  }
}
let passed=false;
try {
  await Promise.race([run(),new Promise((_,reject)=>{watchdog=setTimeout(()=>reject(new Error('Total deadline')),140000);})]);
  passed=true;
}catch{
  process.exitCode=1;
  failurePhase=phase;
  console.error(`RAW FIXTURES FAILED: phase=${failurePhase}; checkpoints=${checks.length}; screenshots=${captures.length}`);
  await captureFailureDiagnostic(failurePhase);
}finally{
  clearTimeout(watchdog);await cleanup();
  if(out){
    await artifact(passed?'report.json':'failure.json',{fixtureOnly:true,mode,passed,matrixExecuted:mode==='matrix',totalPostAttempts:posts.length,phase:failurePhase ?? phase,lastPointer,failureDiagnostic,elapsedMs:Date.now()-started,
      productionUsed:false,modelRequests:0,CSP,posts,interceptions,totalInterceptions:interceptions.length,checks,captures,details,externalCount:external.length,
      runtimeErrorCount:runtimeErrors.length,runtimeErrorCategories:[...runtimeErrors],contrast:'not measured',labelPlacement:'header-title child; actual dimensions in geometry checkpoints',profileRetained:true});
    await artifact('gallery.html','<!doctype html><meta charset="utf-8"><title>RAW fictional fixtures</title><h1>'+label+'</h1><p>Independent fixture evidence, not visual approval. '+(mode==='diagnose-transport'?'Targeted transport diagnostic only; no matrix or full-pass claim. ':'')+(passed?'Requested-mode checks passed.':'Stopped at a failed checkpoint; remaining cases were not reached.')+'</p>'+captures.map(c=>`<figure><figcaption>${c.file} — viewport ${c.viewport.width}×${c.viewport.height}; PNG ${c.png.width}×${c.png.height}</figcaption><a href="${c.file}"><img src="${c.file}" width="680" alt="${c.file}"></a></figure>`).join('')+details.map(c=>`<figure><figcaption>${label} — SUPPLEMENTARY BOTTOM DETAIL, label outside captured UI: ${c.file}; viewport ${c.viewport.width}×${c.viewport.height}; PNG ${c.png.width}×${c.png.height}</figcaption><a href="${c.wrapper}"><img src="${c.file}" width="390" alt="Fictional supplementary bottom detail"></a></figure>`).join('')+(failureDiagnostic.status==='captured' ? '<h2>Failure diagnostic — not a required matrix state</h2><p>Viewport capture at failure; no page repositioning.</p><a href="failure-diagnostic.png"><img src="failure-diagnostic.png" width="680" alt="Failure diagnostic only"></a>' : ''));
    console.log(`RAW FIXTURE ARTIFACTS: ${out}`);
  }
}
