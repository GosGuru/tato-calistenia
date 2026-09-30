import { afterEach, expect, it, vi } from 'vitest';
import { createCompletionSound } from './completionSound';

function audio(state = 'running') {
  const oscillators: ReturnType<typeof oscillator>[] = [];
  const gains: ReturnType<typeof gain>[] = [];
  function oscillator() { return { type: '', frequency: { setValueAtTime: vi.fn() }, connect: vi.fn(), disconnect: vi.fn(), start: vi.fn(), stop: vi.fn(), onended: null as null | (() => void) }; }
  function gain() { return { gain: { setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() }, connect: vi.fn(), disconnect: vi.fn() }; }
  const context = { state, currentTime: 10, destination: {}, resume: vi.fn(() => Promise.resolve()), close: vi.fn(() => Promise.resolve()),
    createOscillator: vi.fn(() => { const node = oscillator(); oscillators.push(node); return node; }),
    createGain: vi.fn(() => { const node = gain(); gains.push(node); return node; }) };
  const constructor = vi.fn(function () { return context; });
  vi.stubGlobal('AudioContext', constructor);
  return { context, constructor, oscillators, gains };
}
afterEach(() => vi.unstubAllGlobals());

it('is inert until armed and plays one finite quiet two-partial envelope per arm', () => {
  const a = audio(); const sound = createCompletionSound();
  expect(a.constructor).not.toHaveBeenCalled();
  const play = sound.arm();
  expect(a.constructor).toHaveBeenCalledTimes(1);
  expect(a.oscillators).toHaveLength(0);
  play(); play();
  expect(a.oscillators).toHaveLength(2);
  expect(a.gains.reduce((sum, g) => sum + g.gain.linearRampToValueAtTime.mock.calls[0][0], 0)).toBeLessThanOrEqual(0.05);
  a.oscillators.forEach((o, i) => {
    expect(o.type).toBe('sine');
    expect(o.frequency.setValueAtTime).toHaveBeenCalledWith([1568, 2352][i], 10);
    expect(o.start).toHaveBeenCalledWith(10);
    expect(o.stop.mock.calls[0][0]).toBeGreaterThan(10);
    expect(o.stop.mock.calls[0][0]).toBeLessThan(10.7);
    expect(a.gains[i].gain.setValueAtTime).toHaveBeenCalledWith(0, 10);
    expect(a.gains[i].gain.linearRampToValueAtTime).toHaveBeenLastCalledWith(0, 10.55);
    o.onended?.();
    expect(o.disconnect).toHaveBeenCalledTimes(1);
    expect(a.gains[i].disconnect).toHaveBeenCalledTimes(1);
  });
  sound.dispose(); sound.dispose();
  expect(a.context.close).toHaveBeenCalledTimes(1);
});

it('consumes a suspended completion without late playback when resume resolves', async () => {
  const a = audio('suspended'); let resolve!: () => void;
  a.context.resume.mockImplementation(() => new Promise<void>(r => { resolve = r; }));
  const sound = createCompletionSound(); const play = sound.arm();
  expect(a.context.resume).toHaveBeenCalledTimes(1);
  play(); a.context.state = 'running'; resolve(); await Promise.resolve(); play();
  expect(a.oscillators).toHaveLength(0);
  sound.arm()(); expect(a.oscillators).toHaveLength(2);
  sound.dispose();
});

it('invalidates older arms, bounds overlapping resources and cannot revive after disposal', async () => {
  const a = audio(); const sound = createCompletionSound();
  const old = sound.arm(); const current = sound.arm(); old();
  expect(a.oscillators).toHaveLength(0); current();
  sound.arm()();
  expect(a.oscillators[0].disconnect).toHaveBeenCalledTimes(1);
  sound.dispose(); sound.arm()(); current();
  expect(a.oscillators).toHaveLength(4);
  a.oscillators.forEach(o => expect(o.disconnect).toHaveBeenCalledTimes(1));
});

it.each(['unsupported', 'constructor', 'resume-throw', 'resume-reject', 'gain', 'oscillator', 'connect', 'start', 'stop', 'disconnect', 'close-throw', 'close-reject'])('silently tolerates %s', async failure => {
  const a = audio(failure.startsWith('resume') ? 'suspended' : 'running');
  function fail(): never { throw new Error('fictional audio failure'); }
  if (failure === 'unsupported') vi.stubGlobal('AudioContext', undefined);
  if (failure === 'constructor') a.constructor.mockImplementation(fail);
  if (failure === 'resume-throw') a.context.resume.mockImplementation(fail);
  if (failure === 'resume-reject') a.context.resume.mockRejectedValue(new Error('fictional'));
  if (failure === 'gain') a.context.createGain.mockImplementation(fail);
  if (failure === 'oscillator') a.context.createOscillator.mockImplementation(fail);
  if (['connect', 'start', 'stop', 'disconnect'].includes(failure)) {
    const original = a.context.createOscillator.getMockImplementation()!;
    a.context.createOscillator.mockImplementation(() => {
      const node = original(); node[failure as 'connect'].mockImplementation(fail); return node;
    });
  }
  if (failure === 'close-throw') a.context.close.mockImplementation(fail);
  if (failure === 'close-reject') a.context.close.mockRejectedValue(new Error('fictional'));
  const sound = createCompletionSound();
  expect(() => { const play = sound.arm(); play(); play(); sound.dispose(); }).not.toThrow();
  await Promise.resolve();
  a.gains.forEach(g => expect(g.disconnect).toHaveBeenCalled());
});

it('does not revive a disposed suspended context after pending resume settles', async () => {
  const a = audio('suspended'); let resolve!: () => void;
  a.context.resume.mockImplementation(() => new Promise<void>(r => { resolve = r; }));
  const sound = createCompletionSound(); const play = sound.arm(); sound.dispose();
  a.context.state = 'running'; resolve(); await Promise.resolve(); play(); sound.arm()();
  expect(a.oscillators).toHaveLength(0); expect(a.constructor).toHaveBeenCalledTimes(1);
});
