// Only invented constants. No CLI text, files of user content, or model quality claim.
import assert from 'node:assert/strict';
import { readdir, stat, readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { loadEngine, partitionQuery, validateVectors, spec } from './embed.mjs';

async function treeBytes(root) {
  let total = 0;
  for (const entry of await readdir(root, { withFileTypes: true })) {
    if (entry.isSymbolicLink()) continue;
    const name = path.join(root, entry.name);
    total += entry.isDirectory() ? await treeBytes(name) : (await stat(name)).size;
  }
  return total;
}

console.log = console.warn = console.error = () => {};
let engine;
const timer = setTimeout(() => {
  process.stdout.write('{"type":"error","code":"smoke_timeout"}\n');
  process.exit(1);
}, 175000);
try {
  const directory = path.dirname(fileURLToPath(import.meta.url));
  const installedBytes = await treeBytes(path.join(directory, 'node_modules'));
  if (installedBytes > 1024**3) throw new Error('footprint_exceeded');
  const runtime = JSON.parse(await readFile(path.join(directory, 'node_modules/@huggingface/transformers/package.json'), 'utf8'));
  const ort = JSON.parse(await readFile(path.join(directory, 'node_modules/onnxruntime-node/package.json'), 'utf8'));
  const sharp = JSON.parse(await readFile(path.join(directory, 'node_modules/sharp/package.json'), 'utf8'));
  assert.equal(runtime.version, spec.runtime_version);
  engine = await loadEngine();
  assert.equal(engine.remoteDisabled, true);
  const query = 'Quiero aprender a moverme con control y sostener la práctica.';
  const chunks = await partitionQuery(query, engine.tokenLength);
  assert.equal(chunks.join(''), query);
  // Tokenizer-only stress verifies complete multi-chunk Unicode coverage.
  const longQuery = 'árbol 🦊 movimiento\r\n'.repeat(1200);
  const longChunks = await partitionQuery(longQuery, engine.tokenLength);
  assert.equal(longChunks.join(''), longQuery);
  assert.ok(longChunks.length > 1);
  for (const chunk of longChunks) assert.ok(await engine.tokenLength(spec.query_prefix + chunk) <= spec.max_tokens);
  const queries = await engine.embed('query', [query]);
  const passages = await engine.embed('passage', ['Comprender el objetivo concreto antes de proponer ayuda.', 'Atender una duda concreta sin repetir la propuesta.']);
  validateVectors(queries.vectors);
  validateVectors(passages.vectors);
  assert.equal(passages.vectors.length, 2);
  await engine.dispose();
  engine = null;
  process.stdout.write(JSON.stringify({
    type: 'smoke', device: 'cpu', remote_models: false, dimensions: 384,
    query_vectors: queries.chunks, passage_vectors: passages.chunks,
    coverage: true, stress_chunks: longChunks.length, installed_bytes: installedBytes,
    runtime: runtime.version, onnxruntime: ort.version, sharp: sharp.version,
  }) + '\n');
} catch (error) {
  const code = ['native_runtime_unavailable', 'footprint_exceeded'].includes(error?.message) ? error.message : 'smoke_failed';
  process.stdout.write(JSON.stringify({ type: 'error', code }) + '\n');
  process.exitCode = 1;
} finally {
  if (engine) await engine.dispose().catch(() => {});
  clearTimeout(timer);
}
