/**
 * Winning Channel Combos (iter159) — top 3 channel combinations by real
 * booked-meeting count. Founders can one-click "duplicate" a combo into a
 * sequence skeleton seeded with the same channel mix.
 */
import React, { useState } from 'react';
import { toast } from 'sonner';
import { Trophy, Copy } from '@phosphor-icons/react';
import api from '../../config/api';
import { SectionCard, ComingSoon } from './dashboard_shared';

const RANK_COLOURS = ['#F59E0B', '#94A3B8', '#A78BFA']; // gold, silver, lavender

export const WinningCombos = ({ combos, onDuplicate }) => {
  const [busy, setBusy] = useState(null);
  if (!combos || combos.coming_soon || !combos.rows?.length) {
    return (
      <SectionCard title="Winning channel combos" sub="Top combinations by booked meetings" testid="winning-combos">
        <ComingSoon what="winning combos" why="Track lead source across 2+ channels and book a meeting to populate." />
      </SectionCard>
    );
  }

  const handleDuplicate = async (combo) => {
    setBusy(combo);
    try {
      const r = await api.post('/api/dashboard/sequences/duplicate-from-combo', { combo });
      toast.success(`Sequence draft created: ${r.data.sequence.name}`, {
        description: 'Wire it up in Lemlist next.',
      });
      onDuplicate?.();
    } catch (e) {
      toast.error(e?.response?.data?.detail || 'Could not duplicate sequence');
    } finally {
      setBusy(null);
    }
  };

  return (
    <SectionCard
      title="Winning channel combos"
      sub="Top 3 channel pairs ranked by booked meetings — duplicate to a new sequence in one click"
      testid="winning-combos"
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {combos.rows.map((c, i) => {
          const colour = RANK_COLOURS[i] || '#94A3B8';
          const isLoading = busy === c.combo;
          return (
            <div
              key={c.combo}
              className="rounded-xl p-4 border transition-all hover:-translate-y-0.5"
              data-testid={`winning-combo-${i + 1}`}
              style={{
                background: `linear-gradient(160deg, ${colour}15, var(--theme-surface) 65%)`,
                borderColor: `${colour}40`,
              }}
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1.5">
                  <Trophy size={14} weight="fill" style={{ color: colour }} />
                  <span className="text-[10px] uppercase font-extrabold tracking-[0.16em]" style={{ color: colour }}>
                    #{i + 1}
                  </span>
                </div>
                <div className="text-[11px] tabular-nums font-bold" style={{ color: 'var(--theme-text)' }}>
                  {c.close_rate}% close
                </div>
              </div>
              <div className="text-sm font-bold capitalize mb-1.5" style={{ color: 'var(--theme-text)' }}>
                {c.combo}
              </div>
              <div className="text-[11px]" style={{ color: 'var(--theme-text-muted)' }}>
                <strong style={{ color: 'var(--theme-text)' }}>{c.bookings}</strong> bookings from {c.leads} leads
              </div>
              <button
                onClick={() => handleDuplicate(c.combo)}
                disabled={isLoading}
                className="mt-3 w-full text-[11px] font-bold px-2.5 py-1.5 rounded-md flex items-center justify-center gap-1.5 transition-all active:scale-95 disabled:opacity-50 hover:brightness-110 focus:outline-none focus:ring-2 focus:ring-offset-1"
                style={{ background: colour, color: '#fff' }}
                data-testid={`winning-combo-duplicate-${i + 1}`}
                aria-label={`Duplicate ${c.combo} as a new sequence`}
              >
                <Copy size={11} weight="bold" /> {isLoading ? 'Creating…' : 'Duplicate to sequence'}
              </button>
            </div>
          );
        })}
      </div>
    </SectionCard>
  );
};

export default WinningCombos;
