/**
 * SSE hook for real-time AI pipeline events.
 *
 * Connects to /ai/api/events/stream and dispatches typed events
 * to registered listeners. Auto-reconnects on disconnect.
 */

import { useState, useEffect, useRef, useCallback } from "react";

const SSE_URL = "/ai/api/events/stream";
const RECONNECT_DELAY = 5000;

export default function useAIEvents(eventTypes = []) {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState(null);
  const listenersRef = useRef({});
  const sourceRef = useRef(null);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
    }

    const es = new EventSource(SSE_URL);
    sourceRef.current = es;

    es.onopen = () => setConnected(true);

    es.onerror = () => {
      setConnected(false);
      es.close();
      // Auto-reconnect
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
    };

    // Listen for specific event types
    const types = eventTypes.length > 0
      ? eventTypes
      : ["pipeline_progress", "review_ready", "writeback_complete", "error", "health"];

    for (const type of types) {
      es.addEventListener(type, (event) => {
        try {
          const data = JSON.parse(event.data);
          const parsed = { type, data, timestamp: new Date() };
          setLastEvent(parsed);

          // Notify registered listeners
          if (listenersRef.current[type]) {
            for (const cb of listenersRef.current[type]) {
              cb(parsed);
            }
          }
        } catch {
          // Ignore malformed events
        }
      });
    }

    // Also handle unnamed messages (keepalive pings, etc.)
    es.onmessage = (event) => {
      if (event.data === ":keepalive") return;
      try {
        const data = JSON.parse(event.data);
        setLastEvent({ type: "message", data, timestamp: new Date() });
      } catch {
        // Ignore
      }
    };
  }, [eventTypes]);

  useEffect(() => {
    connect();
    return () => {
      if (sourceRef.current) sourceRef.current.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [connect]);

  const on = useCallback((type, callback) => {
    if (!listenersRef.current[type]) {
      listenersRef.current[type] = [];
    }
    listenersRef.current[type].push(callback);

    // Return unsubscribe function
    return () => {
      listenersRef.current[type] = listenersRef.current[type].filter(cb => cb !== callback);
    };
  }, []);

  return { connected, lastEvent, on };
}
