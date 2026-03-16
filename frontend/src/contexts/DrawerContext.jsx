import React, { createContext, useContext, useState, useCallback } from "react";

const DrawerContext = createContext(null);

export function DrawerProvider({ children }) {
  const [drawer, setDrawer] = useState({ type: null, data: null, onSaved: null });

  const openDrawer = useCallback((type, data = null, onSaved = null) => {
    setDrawer({ type, data, onSaved });
  }, []);

  const closeDrawer = useCallback(() => {
    setDrawer({ type: null, data: null, onSaved: null });
  }, []);

  return (
    <DrawerContext.Provider value={{ drawer, openDrawer, closeDrawer }}>
      {children}
    </DrawerContext.Provider>
  );
}

export function useDrawer() {
  const ctx = useContext(DrawerContext);
  if (!ctx) throw new Error("useDrawer must be used within DrawerProvider");
  return ctx;
}
