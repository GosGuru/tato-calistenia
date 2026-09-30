export interface CompletionSound {
  arm(): () => void;
  dispose(): void;
}

const ignore = () => {};
const safely = (action: () => void) => { try { action(); } catch { /* Audio is optional. */ } };

// Original synthesized chime; no audio work occurs until a valid user gesture arms it.
export function createCompletionSound(): CompletionSound {
  let context: AudioContext | undefined;
  let disposed = false;
  let sequence = 0;
  const resources = new Set<() => void>();
  const clear = () => { for (const release of resources) release(); };

  return {
    arm() {
      const ticket = ++sequence;
      let consumed = false;
      if (!disposed) safely(() => {
        if (!context && typeof globalThis.AudioContext === 'function') context = new AudioContext();
        // Only request activation here, never schedule a cue from promise settlement.
        if (context?.state === 'suspended') void context.resume().catch(ignore);
      });
      return () => {
        if (consumed || disposed || ticket !== sequence) return;
        consumed = true;
        safely(() => {
          if (!context || context.state !== 'running') return;
          clear();
          const now = context.currentTime;
          try {
            for (const [frequency, peak] of [[1568, 0.03], [2352, 0.015]]) {
              let oscillator: OscillatorNode | undefined;
              let gain: GainNode | undefined;
              const release = () => {
                if (!resources.delete(release)) return;
                if (oscillator) {
                  const node = oscillator;
                  safely(() => { node.onended = null; });
                  safely(() => node.stop());
                  safely(() => node.disconnect());
                }
                if (gain) { const node = gain; safely(() => node.disconnect()); }
              };
              resources.add(release);
              oscillator = context.createOscillator();
              gain = context.createGain();
              oscillator.type = 'sine';
              oscillator.frequency.setValueAtTime(frequency, now);
              gain.gain.setValueAtTime(0, now);
              gain.gain.linearRampToValueAtTime(peak, now + 0.012);
              gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.48);
              gain.gain.linearRampToValueAtTime(0, now + 0.55);
              oscillator.connect(gain);
              gain.connect(context.destination);
              oscillator.onended = release;
              oscillator.start(now);
              oscillator.stop(now + 0.56);
            }
          } catch { clear(); }
        });
      };
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      sequence += 1;
      clear();
      const closing = context;
      context = undefined;
      safely(() => { if (closing) void closing.close().catch(ignore); });
    },
  };
}
