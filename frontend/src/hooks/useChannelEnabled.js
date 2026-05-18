/**
 * useChannelEnabled — single source of truth for "does this tenant care about
 * channel X?". Answers the question:
 *
 *   "If a workspace picked Email + LinkedIn, don't show them WhatsApp widgets.
 *    If they picked WhatsApp + Phone, don't show them email-only KPIs."
 *
 * Behaviour:
 *   - Reads `/api/tenant/sales-channels` ONCE on mount and caches in module scope.
 *   - If no prefs are saved (fresh tenant), `isEnabled()` returns TRUE for every
 *     channel so we don't break the first-login experience.
 *   - Once at least one channel is saved, only those channels are "enabled".
 *
 * Use it from any component that has channel-specific UI:
 *   const { isEnabled, primary, isLoading } = useChannelEnabled();
 *   if (!isEnabled('whatsapp')) return null;
 */
import { useEffect, useState } from 'react';
import api from '../config/api';

let _cache = null;        // { selected_channels, priority_order, primary_channel }
let _fetchPromise = null; // de-dup concurrent fetches

const fetchOnce = () => {
  if (_cache) return Promise.resolve(_cache);
  if (_fetchPromise) return _fetchPromise;
  _fetchPromise = api.get('/api/tenant/sales-channels')
    .then((r) => {
      _cache = r.data || {};
      return _cache;
    })
    .catch(() => {
      _cache = {};
      return _cache;
    })
    .finally(() => { _fetchPromise = null; });
  return _fetchPromise;
};

/** Force-refresh after the user saves new prefs in Settings. */
export function invalidateChannelCache() {
  _cache = null;
  _fetchPromise = null;
}

export function useChannelEnabled() {
  const [prefs, setPrefs] = useState(_cache);
  const [isLoading, setIsLoading] = useState(!_cache);

  useEffect(() => {
    if (_cache) return;
    setIsLoading(true);
    fetchOnce().then((p) => { setPrefs(p); setIsLoading(false); });
  }, []);

  const selected = prefs?.selected_channels || [];
  const hasPrefs = Array.isArray(selected) && selected.length > 0;

  /** Returns true if the channel is enabled for this tenant.
   *  Critically — when no prefs are saved yet, returns TRUE for everything so
   *  fresh workspaces still see the full UI until they configure their channels. */
  const isEnabled = (key) => !hasPrefs || selected.includes(key);

  return {
    isEnabled,
    primary: prefs?.primary_channel || null,
    selected,
    hasPrefs,
    isLoading,
  };
}
