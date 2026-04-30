import { useEffect } from 'react';

/**
 * useSEO — lightweight SEO helper for client-rendered public pages.
 * Sets document.title, meta description, canonical, OG/Twitter tags,
 * and injects JSON-LD schema. Idempotent across navigations.
 *
 * Usage:
 *   useSEO({
 *     title: 'ARIA | AI Sales Assistant',
 *     description: 'ARIA is an AI sales assistant...',
 *     canonical: 'https://app.genleadai.com/aria',
 *     ogImage: 'https://...',
 *     jsonLd: [{...}, {...}],
 *   });
 */
const BASE_URL = 'https://app.genleadai.com';

const upsertMeta = (attr, key, content) => {
  if (!content) return;
  let el = document.head.querySelector(`meta[${attr}="${key}"]`);
  if (!el) {
    el = document.createElement('meta');
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute('content', content);
};

const upsertLink = (rel, href) => {
  if (!href) return;
  let el = document.head.querySelector(`link[rel="${rel}"]`);
  if (!el) {
    el = document.createElement('link');
    el.setAttribute('rel', rel);
    document.head.appendChild(el);
  }
  el.setAttribute('href', href);
};

const JSONLD_ATTR = 'data-seo-jsonld';

export default function useSEO({
  title,
  description,
  canonical,
  ogImage = 'https://genleadai.com/og-image.png',
  ogType = 'website',
  jsonLd = [],
} = {}) {
  useEffect(() => {
    const origTitle = document.title;
    if (title) document.title = title;

    upsertMeta('name', 'description', description);
    upsertMeta('name', 'robots', 'index, follow, max-snippet:-1, max-image-preview:large, max-video-preview:-1');

    // Open Graph
    upsertMeta('property', 'og:title', title);
    upsertMeta('property', 'og:description', description);
    upsertMeta('property', 'og:type', ogType);
    upsertMeta('property', 'og:url', canonical);
    upsertMeta('property', 'og:image', ogImage);
    upsertMeta('property', 'og:site_name', 'GenLeadAI · ARIA');

    // Twitter
    upsertMeta('name', 'twitter:card', 'summary_large_image');
    upsertMeta('name', 'twitter:title', title);
    upsertMeta('name', 'twitter:description', description);
    upsertMeta('name', 'twitter:image', ogImage);

    // Canonical
    upsertLink('canonical', canonical);

    // Inject JSON-LD schema blocks (clear previous first)
    const existing = document.head.querySelectorAll(`script[${JSONLD_ATTR}]`);
    existing.forEach(n => n.parentNode && n.parentNode.removeChild(n));
    const blocks = Array.isArray(jsonLd) ? jsonLd : [jsonLd];
    blocks.filter(Boolean).forEach(obj => {
      const s = document.createElement('script');
      s.setAttribute('type', 'application/ld+json');
      s.setAttribute(JSONLD_ATTR, '1');
      s.textContent = JSON.stringify(obj);
      document.head.appendChild(s);
    });

    return () => {
      document.title = origTitle;
      const toRemove = document.head.querySelectorAll(`script[${JSONLD_ATTR}]`);
      toRemove.forEach(n => n.parentNode && n.parentNode.removeChild(n));
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [title, description, canonical, ogImage, ogType, JSON.stringify(jsonLd)]);
}

export { BASE_URL };
