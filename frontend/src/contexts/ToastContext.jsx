import React, { createContext, useContext } from "react";
import * as ToastPrimitive from "@radix-ui/react-toast";
import useToast from "../hooks/useToast";
import ToastContainer, { ToastViewport } from "../components/shared/Toast";

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const toast = useToast();

  return (
    <ToastPrimitive.Provider>
      <ToastContext.Provider value={toast}>
        {children}
        <ToastContainer toasts={toast.toasts} onRemove={toast.removeToast} />
        <ToastViewport />
      </ToastContext.Provider>
    </ToastPrimitive.Provider>
  );
}

export function useToastContext() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToastContext must be used within ToastProvider");
  return ctx;
}
