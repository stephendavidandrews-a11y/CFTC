import { useState, useCallback } from "react";

let toastId = 0;

export default function useToast() {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((message, type = "success") => {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, message, type }]);
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const success = useCallback((msg) => addToast(msg, "success"), [addToast]);
  const error   = useCallback((msg) => addToast(msg, "error"),   [addToast]);
  const warning = useCallback((msg) => addToast(msg, "warning"), [addToast]);
  const info    = useCallback((msg) => addToast(msg, "info"),    [addToast]);

  return { toasts, addToast, removeToast, success, error, warning, info };
}
