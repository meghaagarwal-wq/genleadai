import React from 'react';
import { Fire, Thermometer, Snowflake } from '@phosphor-icons/react';

/**
 * AriaConfidenceDial — circular SVG gauge showing 0-100 score.
 *
 * Three sizes: sm (28px, list rows), md (60px, lead cards), lg (96px, detail header).
 * Tooltip-style title attribute shows top factors on hover.
 */
const COLOR = {
  green: { ring: '#16A34A', bg: '#16A34A1A', icon: Fire, label: 'Hot' },
  yellow: { ring: '#E2B96F', bg: '#E2B96F1A', icon: Thermometer, label: 'Warm' },
  red: { ring: '#94A3B8', bg: '#94A3B81A', icon: Snowflake, label: 'Cold' },
};

const SIZES = {
  sm: { px: 28, stroke: 3, font: 9, iconSize: 9 },
  md: { px: 60, stroke: 5, font: 16, iconSize: 12 },
  lg: { px: 96, stroke: 8, font: 24, iconSize: 16 },
};

const AriaConfidenceDial = ({ score = 0, color = 'red', size = 'md', factors = [], showLabel = false }) => {
  const cfg = SIZES[size] || SIZES.md;
  const meta = COLOR[color] || COLOR.red;
  const Icon = meta.icon;
  const radius = (cfg.px - cfg.stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.min(100, Math.max(0, score)) / 100) * circumference;

  const tip = factors?.length
    ? `Aria confidence: ${score}/100 (${meta.label})\n` +
      factors.map((f) => `${f.delta > 0 ? '+' : ''}${f.delta} · ${f.label}`).join('\n')
    : `Aria confidence: ${score}/100`;

  return (
    <div className="inline-flex items-center gap-2" data-testid={`aria-confidence-${score}`} title={tip}>
      <div className="relative inline-flex items-center justify-center" style={{ width: cfg.px, height: cfg.px }}>
        <svg width={cfg.px} height={cfg.px} className="rotate-[-90deg]">
          <circle cx={cfg.px / 2} cy={cfg.px / 2} r={radius} stroke={meta.bg} strokeWidth={cfg.stroke} fill="none" />
          <circle
            cx={cfg.px / 2} cy={cfg.px / 2} r={radius}
            stroke={meta.ring} strokeWidth={cfg.stroke} fill="none"
            strokeDasharray={circumference} strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: 'stroke-dashoffset 600ms ease-out' }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {size !== 'sm' && <Icon size={cfg.iconSize} weight="fill" style={{ color: meta.ring }} />}
          <span className="font-extrabold font-mono leading-none" style={{ fontSize: cfg.font, color: meta.ring, fontFamily: 'JetBrains Mono' }}>{score}</span>
        </div>
      </div>
      {showLabel && (
        <div className="flex flex-col">
          <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[#9B8AB0]">Aria confidence</span>
          <span className="text-sm font-bold" style={{ color: meta.ring }}>{meta.label} · {score}/100</span>
        </div>
      )}
    </div>
  );
};

export default AriaConfidenceDial;
