import { createContext, useContext, useEffect, useState } from 'react';

/**
 * WorkspaceContext — persistent workspace switcher.
 *
 * Multi-tenant ready: each workspace has a slug, label, color and
 * a route prefix. Adding a new workspace = adding a new entry here.
 */
export const WORKSPACES = [
  {
    slug: 'aria_crm',
    label: 'ARIA',
    sub: 'AI Sales CRM',
    color: '#7C35DC',
    accent: '#C044E0',
    home: '/',
  },
  {
    slug: 'pietential',
    label: 'Aria for Pietential',
    sub: 'Wellbeing Engagement Intelligence',
    color: '#7C35DC',
    accent: '#C044E0',
    home: '/pt',
  },
];

const STORAGE_KEY = 'aria.activeWorkspace';

const Ctx = createContext({ active: WORKSPACES[0], setActive: () => {} });

export const WorkspaceProvider = ({ children }) => {
  const [active, setActiveState] = useState(() => {
    if (typeof window === 'undefined') return WORKSPACES[0];
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return WORKSPACES.find(w => w.slug === saved) || WORKSPACES[0];
  });

  const setActive = (slugOrObj) => {
    const next = typeof slugOrObj === 'string'
      ? WORKSPACES.find(w => w.slug === slugOrObj)
      : slugOrObj;
    if (!next) return;
    setActiveState(next);
    if (typeof window !== 'undefined') window.localStorage.setItem(STORAGE_KEY, next.slug);
  };

  // Re-read on storage event (cross-tab sync)
  useEffect(() => {
    const handler = (e) => {
      if (e.key === STORAGE_KEY && e.newValue) {
        const next = WORKSPACES.find(w => w.slug === e.newValue);
        if (next) setActiveState(next);
      }
    };
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, []);

  return <Ctx.Provider value={{ active, setActive, workspaces: WORKSPACES }}>{children}</Ctx.Provider>;
};

export const useWorkspace = () => useContext(Ctx);
