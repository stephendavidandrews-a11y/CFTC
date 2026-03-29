/**
 * Generic API fetching hook.
 *
 * Uses a request counter to prevent stale responses from overwriting
 * fresh data when deps change rapidly (race condition guard).
 */

import { useState, useEffect, useCallback, useRef } from "react";

export default function useApi(fetchFn, deps = [], { refetchOnFocus = false } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const hasFetched = useRef(false);
  const requestId = useRef(0);

  const refetch = useCallback(() => {
    const thisRequest = ++requestId.current;
    setLoading(true);
    setError(null);
    return fetchFn()
      .then((result) => {
        if (thisRequest === requestId.current) {
          setData(result);
        }
        return result;
      })
      .catch((err) => {
        if (thisRequest === requestId.current) {
          setError(err);
        }
      })
      .finally(() => {
        if (thisRequest === requestId.current) {
          setLoading(false);
        }
        hasFetched.current = true;
      });
  // eslint-disable-next-line
  }, deps);

  useEffect(() => { refetch(); }, [refetch]);

  useEffect(() => {
    if (!refetchOnFocus) return;
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible" && hasFetched.current) {
        refetch();
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);
    return () => document.removeEventListener("visibilitychange", onVisibilityChange);
  }, [refetchOnFocus, refetch]);

  return { data, loading, error, refetch };
}

// Also export as named for backward compatibility
export { useApi };
