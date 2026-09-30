import test from 'node:test';
import assert from 'node:assert/strict';
import { partitionQuery, prepareTexts, validateVectors } from './embed.mjs';

const length = async text => Array.from(text).length + 2;

test('lossless Unicode chunks include prefix and specials in limit', async () => {
  const text = 'á🦊\r\n '.repeat(900);
  const chunks = await partitionQuery(text, length);
  assert.equal(chunks.join(''), text);
  assert.ok(chunks.length > 1);
  for (const chunk of chunks) assert.ok(await length('query: ' + chunk) <= 512);
});
test('reject overlong passage, do not truncate', async () => {
  await assert.rejects(prepareTexts('passage', ['a'.repeat(510)], length));
  assert.deepEqual(await prepareTexts('passage', ['invented'], length), ['passage: invented']);
});
test('fail closed for character and chunk budgets', async () => {
  await assert.rejects(partitionQuery('a'.repeat(24001), length));
  await assert.rejects(partitionQuery('a'.repeat(200), async text => text.length > 8 ? 513 : 3));
  await assert.rejects(partitionQuery('\ud800', length));
});
test('validate dimensions, finite numbers, unit norm', () => {
  validateVectors([[1, ...Array(383).fill(0)]]);
  for (const vector of [Array(384).fill(0), Array(384).fill(NaN), [1]]) {
    assert.throws(() => validateVectors([vector]));
  }
});
