import { readFile, stat } from 'node:fs/promises';
import { createReadStream } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

export let spec;
try {
  spec = JSON.parse(await readFile(new URL('./model_manifest.json', import.meta.url), 'utf8'));
} catch {
  process.stdout.write('{"type":"error","code":"model_manifest_unavailable"}\n');
  process.exit(1);
}
export const modelPath = `C:/Users/Maxim/AppData/Local/TatoEditorialRag/models/${spec.model}/${spec.revision}`;
const fail = () => { throw new Error('embedding_unavailable'); };

function checkText(text) {
  if (typeof text !== 'string' || !text.length || Array.from(text).length > spec.max_query_chars || /[\uD800-\uDFFF]/u.test(text)) fail();
}

export async function partitionQuery(text, tokenLength) {
  checkText(text);
  const chunks = [];
  // Recursive halves do not assume tokenizer length is monotonic in text length.
  async function split(value) {
    if (chunks.length >= spec.max_chunks) fail();
    const count = await tokenLength(spec.query_prefix + value);
    if (!Number.isInteger(count) || count < 1) fail();
    if (count <= spec.max_tokens) {
      chunks.push(value);
      return;
    }
    const points = Array.from(value);
    if (points.length < 2) fail();
    const middle = Math.floor(points.length / 2);
    await split(points.slice(0, middle).join(''));
    await split(points.slice(middle).join(''));
  }
  await split(text);
  if (chunks.join('') !== text) fail();
  return chunks;
}

export async function prepareTexts(mode, texts, tokenLength) {
  if (!Array.isArray(texts)) fail();
  if (mode === 'query') {
    if (texts.length !== 1) fail();
    return (await partitionQuery(texts[0], tokenLength)).map(text => spec.query_prefix + text);
  }
  if (mode !== 'passage' || texts.length < 1 || texts.length > spec.max_passages) fail();
  const result = [];
  for (const text of texts) {
    checkText(text);
    const prefixed = spec.passage_prefix + text;
    const count = await tokenLength(prefixed);
    if (!Number.isInteger(count) || count < 1 || count > spec.max_tokens) fail();
    result.push(prefixed);
  }
  return result;
}

export function validateVectors(vectors) {
  if (!Array.isArray(vectors) || !vectors.length || vectors.length > spec.max_chunks) fail();
  for (const vector of vectors) {
    if (!Array.isArray(vector) || vector.length !== spec.dimensions || vector.some(x => typeof x !== 'number' || !Number.isFinite(x))) fail();
    if (Math.abs(Math.sqrt(vector.reduce((sum, x) => sum + x*x, 0)) - 1) > 1e-4) fail();
  }
}

export async function verifyAssets(root) {
  if (path.resolve(root) !== path.resolve(modelPath)) fail();
  for (const file of spec.files) {
    const filename = path.join(root, file.path);
    if ((await stat(filename)).size !== file.size) fail();
    const digest = createHash(file.hash_kind === 'sha256' ? 'sha256' : 'sha1');
    if (file.hash_kind === 'git_blob_sha1') digest.update(`blob ${file.size}\0`);
    for await (const block of createReadStream(filename)) digest.update(block);
    if (digest.digest('hex') !== file.hash) fail();
  }
}

export async function loadEngine(root = modelPath) {
  await verifyAssets(root);
  let runtime;
  try {
    runtime = await import('@huggingface/transformers');
  } catch {
    throw new Error('native_runtime_unavailable');
  }
  const { env, AutoTokenizer, AutoModel, mean_pooling } = runtime;
  env.allowRemoteModels = false;
  env.allowLocalModels = true;
  env.localModelPath = root;
  env.useFSCache = false;
  env.useBrowserCache = false;
  env.useCustomCache = false;
  const options = { local_files_only: true, revision: spec.revision };
  const tokenizer = await AutoTokenizer.from_pretrained(root, options);
  const model = await AutoModel.from_pretrained(root, {
    ...options, device: 'cpu', dtype: 'q8',
    session_options: { logSeverityLevel: 3, intraOpNumThreads: 2, interOpNumThreads: 1 },
  });
  const tokenLength = async text => tokenizer(text, {
    add_special_tokens: true, truncation: false, padding: false, return_tensor: false,
  }).input_ids.length;
  return {
    tokenLength,
    remoteDisabled: env.allowRemoteModels === false,
    async embed(mode, texts) {
      const prepared = await prepareTexts(mode, texts, tokenLength);
      const vectors = [];
      // Sequential bounded inputs avoid large padded query batches.
      for (const text of prepared) {
        const inputs = tokenizer(text, { add_special_tokens: true, padding: false, truncation: false });
        if (inputs.input_ids.dims.at(-1) > spec.max_tokens) fail();
        const output = await model(inputs);
        const pooled = mean_pooling(output.last_hidden_state, inputs.attention_mask).normalize(2, -1);
        vectors.push(pooled.tolist()[0]);
      }
      validateVectors(vectors);
      return { type: 'embeddings', vectors, chunks: vectors.length };
    },
    async dispose() { await model.dispose(); },
  };
}

async function main() {
  // Third-party diagnostics must not echo input; CLI stdout is typed JSON only.
  console.log = console.warn = console.error = () => {};
  let engine;
  const timer = setTimeout(() => {
    process.stdout.write('{"type":"error","code":"embedding_timeout"}\n');
    process.exit(1);
  }, 175000);
  try {
    const buffers = [];
    let size = 0;
    for await (const block of process.stdin) {
      size += block.length;
      if (size > 1500000) fail();
      buffers.push(block);
    }
    const request = JSON.parse(Buffer.concat(buffers).toString('utf8'));
    if (!request || Object.keys(request).sort().join(',') !== 'mode,model_path,texts') fail();
    if (request.model_path !== modelPath.replaceAll('/', '\\') && request.model_path !== modelPath) fail();
    if (!['query', 'passage'].includes(request.mode)) fail();
    engine = await loadEngine(modelPath);
    const result = await engine.embed(request.mode, request.texts);
    await engine.dispose();
    engine = null;
    process.stdout.write(JSON.stringify(result) + '\n');
  } catch (error) {
    const code = error?.message === 'native_runtime_unavailable' ? 'native_runtime_unavailable' : 'embedding_unavailable';
    process.stdout.write(JSON.stringify({ type: 'error', code }) + '\n');
    process.exitCode = 1;
  } finally {
    if (engine) await engine.dispose().catch(() => {});
    clearTimeout(timer);
  }
}

if (process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url) await main();
