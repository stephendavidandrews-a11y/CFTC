/**
 * Simple in-memory API response cache with TTL.
 *
 * Prevents redundant fetches for frequently-accessed, rarely-changing data
 * like enums, people lists, and org lists. Cache entries expire after
 * TTL_MS and are automatically refreshed on next access.
 */

const TTL_MS = 5 * 60 * 1000; // 5 minutes
const cache = new Map();

/**
 * Wrap an async fetch function with caching.
 * Same args produce same cache key (via JSON.stringify).
 *
 * @param {string} prefix - Cache key namespace (e.g., 'enum', 'people')
 * @param {Function} fetchFn - Async function that returns data
 * @param  {...any} args - Arguments passed to fetchFn (also used as cache key)
 * @returns {Promise} Cached or fresh data
 */
export function cachedFetch(prefix, fetchFn, ...args) {
  const key = prefix + ':' + JSON.stringify(args);
  const entry = cache.get(key);

  if (entry && Date.now() - entry.ts < TTL_MS) {
    return Promise.resolve(entry.data);
  }

  // If there's already an in-flight request for this key, reuse it
  if (entry && entry.pending) {
    return entry.pending;
  }

  const pending = fetchFn(...args).then((data) => {
    cache.set(key, { data, ts: Date.now(), pending: null });
    return data;
  }).catch((err) => {
    // On error, clear the pending state so next call retries
    const e = cache.get(key);
    if (e) e.pending = null;
    throw err;
  });

  cache.set(key, { ...(entry || {}), pending });
  return pending;
}

/** Clear all cached entries (e.g., after a write operation). */
export function clearCache(prefix) {
  if (prefix) {
    for (const key of cache.keys()) {
      if (key.startsWith(prefix + ':')) cache.delete(key);
    }
  } else {
    cache.clear();
  }
}
