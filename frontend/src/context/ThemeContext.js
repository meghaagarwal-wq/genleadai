/**
 * ThemeContext — dark / light mode toggle persisted to localStorage.
 *
 * Default: dark (per ARIA Dashboard spec).
 * Sets `data-theme` on <html> so CSS variables swap globally.
 * Persistence: localStorage.aria_theme ("dark" | "light").
 */
import { createContext, useContext, useEffect, useState, useCallback } from 'react';

const ThemeContext = createContext({ theme: 'dark', toggle: () => {}, setTheme: () => {} });

const STORAGE_KEY = 'aria_theme';

const readInitial = () => {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v === 'dark' || v === 'light') return v;
  } catch (_) { /* SSR / locked storage */ }
  return 'dark';
};

export const ThemeProvider = ({ children }) => {
  const [theme, setThemeState] = useState(readInitial);

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = theme;
    try { localStorage.setItem(STORAGE_KEY, theme); } catch (_) { /* ignore */ }
  }, [theme]);

  const setTheme = useCallback((next) => {
    if (next === 'dark' || next === 'light') setThemeState(next);
  }, []);

  const toggle = useCallback(() => {
    setThemeState((t) => (t === 'dark' ? 'light' : 'dark'));
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, toggle, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};

export const useTheme = () => useContext(ThemeContext);
