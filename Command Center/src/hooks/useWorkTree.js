/**
 * Hook for building work item trees, computing progress, and managing expand state.
 */

import { useState, useCallback, useMemo, useEffect } from "react";

const STORAGE_KEY = "work_expand_state";

function loadExpandState() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveExpandState(state) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {}
}

export function buildTree(items) {
  const map = {};
  const roots = [];
  items.forEach((item) => {
    map[item.id] = { ...item, children: [] };
  });
  items.forEach((item) => {
    if (item.parent_id && map[item.parent_id]) {
      map[item.parent_id].children.push(map[item.id]);
    } else {
      roots.push(map[item.id]);
    }
  });
  const sortChildren = (nodes) => {
    nodes.sort((a, b) => a.sort_order - b.sort_order);
    nodes.forEach((n) => sortChildren(n.children));
  };
  sortChildren(roots);
  return roots;
}

export function computeProgress(item) {
  if (!item.children || item.children.length === 0) {
    return {
      completed: item.status === "completed" ? 1 : 0,
      total: 1,
    };
  }
  let completed = 0;
  let total = 0;
  item.children.forEach((child) => {
    const cp = computeProgress(child);
    completed += cp.completed;
    total += cp.total;
  });
  return { completed, total };
}

export function effectiveDeadline(item) {
  const dates = [];
  if (item.due_date && item.status !== "completed") {
    dates.push(item.due_date);
  }
  if (item.children) {
    item.children.forEach((child) => {
      if (child.status !== "completed") {
        const d = effectiveDeadline(child);
        if (d) dates.push(d);
      }
    });
  }
  return dates.length > 0 ? dates.sort()[0] : null;
}

export default function useWorkTree() {
  const [expandState, setExpandState] = useState(loadExpandState);

  useEffect(() => {
    saveExpandState(expandState);
  }, [expandState]);

  const toggleExpand = useCallback((key) => {
    setExpandState((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      return next;
    });
  }, []);

  const isExpanded = useCallback(
    (key) => !!expandState[key],
    [expandState]
  );

  const expandAll = useCallback((keys) => {
    setExpandState((prev) => {
      const next = { ...prev };
      keys.forEach((k) => { next[k] = true; });
      return next;
    });
  }, []);

  const collapseAll = useCallback(() => {
    setExpandState({});
  }, []);

  return { toggleExpand, isExpanded, expandAll, collapseAll };
}
