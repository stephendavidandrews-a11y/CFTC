import { useState, useEffect } from "react";
import useApi from "./useApi";

export default function useLazyTab(tabKey, activeTab, fetchFn, deps = []) {
  const [activated, setActivated] = useState(false);

  useEffect(() => {
    if (activeTab === tabKey && !activated) setActivated(true);
  }, [activeTab, tabKey, activated]);

  const { data, loading, error, refetch } = useApi(
    activated ? fetchFn : () => Promise.resolve(null),
    [activated, ...deps]
  );

  return { data, loading: activated ? loading : false, error, refetch, activated };
}
