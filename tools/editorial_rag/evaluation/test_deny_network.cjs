'use strict';
// Replace real capabilities BEFORE loading the fence: even RED cannot perform I/O.
const test = require('node:test');
const assert = require('node:assert/strict');
let originalsCalled = 0;
const sentinel = () => { originalsCalled++; throw new Error('INERT_ORIGINAL'); };
const surfaces = [];
function collect(object, names, family) {
  for (const name of names) {
    if (typeof object[name] === 'function') {
      object[name] = sentinel;
      surfaces.push([object, name, `${family}.${name}`]);
    }
  }
}
for (const name of ['http', 'https']) {
  const api = require(`node:${name}`);
  collect(api, ['request', 'get', 'ClientRequest', 'createServer'], name);
  collect(api.Server.prototype, ['listen'], `${name}.Server`);
}
const net = require('node:net');
collect(net, ['connect', 'createConnection', 'createServer'], 'net');
collect(net.Socket.prototype, ['connect'], 'net.Socket');
collect(net.Server.prototype, ['listen'], 'net.Server');
const tls = require('node:tls');
collect(tls, ['connect', 'createServer'], 'tls');
collect(tls.TLSSocket.prototype, ['connect'], 'tls.TLSSocket');
collect(tls.Server.prototype, ['listen'], 'tls.Server');
const h2 = require('node:http2');
collect(h2, ['connect', 'createServer', 'createSecureServer'], 'http2');
const udp = require('node:dgram');
collect(udp, ['createSocket'], 'dgram');
collect(udp.Socket.prototype, ['connect', 'send', 'bind'], 'dgram.Socket');
const dns = require('node:dns');
const dnsNames = ['lookup', 'lookupService', 'resolve', 'resolve4', 'resolve6',
  'resolveAny', 'resolveCaa', 'resolveCname', 'resolveMx', 'resolveNaptr',
  'resolveNs', 'resolvePtr', 'resolveSoa', 'resolveSrv', 'resolveTxt', 'resolveTlsa', 'reverse'];
collect(dns, dnsNames, 'dns');
collect(dns.Resolver.prototype, dnsNames, 'dns.Resolver');
collect(dns.promises, dnsNames, 'dns.promises');
collect(dns.promises.Resolver.prototype, dnsNames, 'dns.promises.Resolver');
collect(require('node:child_process'), ['spawn', 'spawnSync', 'exec', 'execSync',
  'execFile', 'execFileSync', 'fork'], 'child_process');
collect(require('node:child_process').ChildProcess.prototype, ['spawn'], 'child_process.ChildProcess');
collect(require('node:worker_threads'), ['Worker'], 'worker_threads');
globalThis.fetch = sentinel;
let diagnostic = '';
const originalWrite = process.stderr.write;
process.stderr.write = function(chunk) { diagnostic += String(chunk); return true; };
const previousExitListeners = process.listeners('exit');
let loadError;
try { require('./deny_network.cjs'); } catch (error) { loadError = error; }

test('guard loads before any capability and reports startup', () => {
  assert.ifError(loadError);
  assert.match(diagnostic, /TATO_FENCE.*startup/);
});
test('all instrumented families deny without calling an original', async () => {
  for (const [object, name, label] of surfaces) {
    if (label.startsWith('dns.promises')) {
      await assert.rejects(object[name]('example.invalid'), /TATO_DENIED/, label);
    } else {
      assert.throws(() => object[name]('example.invalid'), /TATO_DENIED/, label);
    }
  }
  assert.equal(originalsCalled, 0);
});
test('fetch rejects asynchronously and redacts URL credentials and payload', async () => {
  let promise;
  assert.doesNotThrow(() => {
    promise = fetch('https://USER:SECRET@r.promptfoo.app/private-path?secret=TOKEN',
      {headers: {authorization: 'HEADER'}, body: 'PROMPT_BODY'});
  });
  assert.ok(promise instanceof Promise);
  await assert.rejects(promise, /TATO_DENIED/);
  assert.match(diagnostic, /https:\/\/r\.promptfoo\.app/);
  assert.doesNotMatch(diagnostic, /USER|SECRET|private-path|TOKEN|HEADER|PROMPT_BODY/);
  assert.equal(originalsCalled, 0);
});
test('Worker construction is denied and diagnostic lines are bounded', () => {
  assert.throws(() => new (require('node:worker_threads').Worker)('PRIVATE_SCRIPT'), /TATO_DENIED/);
  assert.doesNotMatch(diagnostic, /PRIVATE_SCRIPT/);
  assert.ok(diagnostic.split('\n').every(line => line.length < 1000));
});
test('attempts are bounded, counts survive truncation and ESM exports are fenced', async () => {
  const esm = await import('node:net');
  assert.throws(() => esm.connect({host: 'example.invalid', port: 443}), /TATO_DENIED/);
  for (let index = 0; index < 150; index++) {
    await assert.rejects(fetch('https://example.invalid/path?SECRET'), /TATO_DENIED/);
  }
  const listener = process.listeners('exit').find(item => !previousExitListeners.includes(item));
  assert.equal(typeof listener, 'function');
  listener();
  const events = diagnostic.trim().split('\n').map(line => JSON.parse(line.slice('TATO_FENCE '.length)));
  assert.equal(events.filter(event => event.event === 'blocked').length, 128);
  const end = events.at(-1);
  assert.equal(end.event, 'exit');
  assert.ok(end.total > 150);
  assert.ok(end.forbidden > 0);
  assert.equal(end.total, Object.values(end.counts).reduce((a, b) => a + b, 0));
  assert.equal(originalsCalled, 0);
  assert.doesNotMatch(diagnostic, /SECRET/);
  process.stderr.write = originalWrite;
});
