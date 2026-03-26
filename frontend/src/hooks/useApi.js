/**
 * Generic API fetching hook.
 */

import { useState, useEffect, useCallback, useRef } from "react";

export default function useApi(fetchFn, deps = [], { refetchOnFocus = false } = {}) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const hasFetched = useRef(false);

  const refetch = useCallback(() => {
    setLoading(true);
    setError(null);
    return fetchFn()
      .then((result) => { setData(result); return result; })
      .catch(setError)
      .finally(() => {
        setLoading(false);
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
