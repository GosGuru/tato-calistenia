'use strict';
// Node API instrumentation, NOT an OS sandbox or a defense against native code.
const { syncBuiltinESMExports } = require('node:module');
const write = process.stderr.write.bind(process.stderr);
const counts = Object.create(null);
let total = 0;
let forbidden = 0;
const LIMIT = 128;
function emit(value) { write(`TATO_FENCE ${JSON.stringify(value)}\n`); }
function destination(args) {
  try {
    const first = args[0];
    const value = typeof first === 'string' ? first : first instanceof URL ? first.href : first?.url;
    if (typeof value === 'string' && /^https?:\/\//i.test(value)) {
      const url = new URL(value);
      return url.origin.slice(0, 180);
    }
    const host = first && typeof first === 'object' ? first.hostname || first.host :
      typeof first === 'number' ? args[1] : first;
    const port = first && typeof first === 'object' ? first.port : typeof first === 'number' ? first : null;
    if (typeof host === 'string' && /^[a-zA-Z0-9.[\]:-]{1,180}$/.test(host)) {
      return host + (Number.isInteger(Number(port)) && Number(port) > 0 && Number(port) < 65536 ? `:${port}` : '');
    }
  } catch { /* Never stringify arbitrary arguments. */ }
  return 'unavailable';
}
function callsite() {
  for (const line of (new Error().stack || '').split('\n')) {
    const match = line.replaceAll('\\', '/').match(/node_modules\/((?:@[\w.-]+\/)?[\w.-]+\/[\w./-]+):(\d+):\d+/);
    if (match) return `node_modules/${match[1]}:${match[2]}`.slice(0, 240);
  }
  return 'unavailable';
}
function denied(api, args, special) {
  total++;
  counts[api] = (counts[api] || 0) + 1;
  if (special) forbidden++;
  if (total <= LIMIT) emit({event: 'blocked', api, destination: special ? 'withheld' : destination(args), callsite: callsite()});
  const error = new Error(`TATO_DENIED ${api}`);
  error.code = 'TATO_DENIED';
  return error;
}
function patch(object, names, family, special = false, promise = false) {
  for (const name of names) {
    if (typeof object[name] !== 'function') continue;
    object[name] = function(...args) {
      const error = denied(`${family}.${name}`, args, special);
      if (promise) return Promise.reject(error);
      throw error;
    };
  }
}
globalThis.fetch = function(...args) { return Promise.reject(denied('fetch', args, false)); };
for (const name of ['http', 'https']) {
  const api = require(`node:${name}`);
  patch(api, ['request', 'get', 'ClientRequest'], name);
  patch(api, ['createServer'], name, true);
  patch(api.Server.prototype, ['listen'], `${name}.Server`, true);
}
const net = require('node:net');
patch(net, ['connect', 'createConnection'], 'net');
patch(net.Socket.prototype, ['connect'], 'net.Socket');
patch(net, ['createServer'], 'net', true);
patch(net.Server.prototype, ['listen'], 'net.Server', true);
const tls = require('node:tls');
patch(tls, ['connect'], 'tls');
patch(tls.TLSSocket.prototype, ['connect'], 'tls.TLSSocket');
patch(tls, ['createServer'], 'tls', true);
patch(tls.Server.prototype, ['listen'], 'tls.Server', true);
const h2 = require('node:http2');
patch(h2, ['connect'], 'http2');
patch(h2, ['createServer', 'createSecureServer'], 'http2', true);
const udp = require('node:dgram');
patch(udp, ['createSocket'], 'dgram');
patch(udp.Socket.prototype, ['connect', 'send'], 'dgram.Socket');
patch(udp.Socket.prototype, ['bind'], 'dgram.Socket', true);
const dns = require('node:dns');
const names = ['lookup', 'lookupService', 'resolve', 'resolve4', 'resolve6',
  'resolveAny', 'resolveCaa', 'resolveCname', 'resolveMx', 'resolveNaptr',
  'resolveNs', 'resolvePtr', 'resolveSoa', 'resolveSrv', 'resolveTxt', 'resolveTlsa', 'reverse'];
patch(dns, names, 'dns');
patch(dns.Resolver.prototype, names, 'dns.Resolver');
patch(dns.promises, names, 'dns.promises', false, true);
patch(dns.promises.Resolver.prototype, names, 'dns.promises.Resolver', false, true);
const child = require('node:child_process');
patch(child, ['spawn', 'spawnSync', 'exec', 'execSync', 'execFile', 'execFileSync', 'fork'], 'child_process', true);
patch(child.ChildProcess.prototype, ['spawn'], 'child_process.ChildProcess', true);
patch(require('node:worker_threads'), ['Worker'], 'worker_threads', true);
syncBuiltinESMExports();
process.on('exit', () => emit({event: 'exit', total, forbidden, counts}));
emit({event: 'startup', version: 1});
