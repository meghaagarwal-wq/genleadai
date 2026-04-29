import React from 'react';
import { Lock } from '@phosphor-icons/react';
import { usePlan } from '../context/PlanContext';

/**
 * Inline lock/upgrade chip that opens the upgrade modal when clicked.
 * Use as a button next to (or replacing) any feature-gated UI element.
 */
const LockBadge = ({ featureKey, label = 'Upgrade', size = 'sm' }) => {
  const { hasFeature, openUpgrade } = usePlan();
  if (hasFeature(featureKey)) return null;
  const sizeClasses = size === 'lg' ? 'px-3 py-1.5 text-xs' : 'px-2 py-0.5 text-[10px]';
  return (
    <button
      onClick={(e) => { e.stopPropagation(); openUpgrade(featureKey); }}
      className={`inline-flex items-center gap-1 font-bold uppercase tracking-wider rounded border bg-[#F4F0FF] text-[#7C35DC] border-[#7C35DC]/30 hover:bg-[#E0D4F7] transition-colors ${sizeClasses}`}
      data-testid={`lock-badge-${featureKey}`}
      title={`Upgrade to unlock ${featureKey}`}
    >
      <Lock size={size === 'lg' ? 12 : 9} weight="fill" /> {label}
    </button>
  );
};

export default LockBadge;
