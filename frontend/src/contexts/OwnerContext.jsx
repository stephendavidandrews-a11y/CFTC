import React, { createContext, useContext, useState, useEffect } from "react";
import { getSystemConfig } from "../api/tracker";

const OwnerContext = createContext(null);

export function OwnerProvider({ children }) {
  const [ownerId, setOwnerId] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSystemConfig()
      .then((cfg) => {
        setOwnerId(cfg.owner_person_id || null);
      })
      .catch((err) => {
        console.error("Failed to load system config:", err);
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <OwnerContext.Provider value={{ ownerId, ownerLoading: loading }}>
      {children}
    </OwnerContext.Provider>
  );
}

export function useOwner() {
  const ctx = useContext(OwnerContext);
  if (!ctx) throw new Error("useOwner must be used within OwnerProvider");
  return ctx;
}
