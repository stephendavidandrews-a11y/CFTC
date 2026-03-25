import { useSearchParams } from "react-router-dom";

export default function useTabState(defaultTab) {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || defaultTab;
  const setTab = (t) => setParams({ tab: t }, { replace: true });
  return [tab, setTab];
}
