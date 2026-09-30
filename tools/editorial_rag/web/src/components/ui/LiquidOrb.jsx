import React from 'react';

/**
 * LiquidOrb component inspired by lersent001.github.io/orb.
 * Pure SVG/CSS fluid glowing orb with animated organic swirl and atmospheric radial aura.
 */
export function LiquidOrb({ size = 44, className = '', active = true }) {
  return (
    <div
      className={`liquid-orb ${active ? 'is-active' : ''} ${className}`}
      style={{ width: `${size}px`, height: `${size}px` }}
      aria-hidden="true"
    >
      <div className="liquid-orb-glow" />
      <div className="liquid-orb-sphere">
        <div className="liquid-orb-layer orb-layer-1" />
        <div className="liquid-orb-layer orb-layer-2" />
        <div className="liquid-orb-layer orb-layer-3" />
        <div className="liquid-orb-core" />
        <div className="liquid-orb-specular" />
      </div>
    </div>
  );
}

export default LiquidOrb;
