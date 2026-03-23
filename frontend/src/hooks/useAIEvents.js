/**
 * SSE hook for real-time AI pipeline events.
 *
 * Connects to /ai/api/events/stream and dispatches typed events
 * to registered listeners. Auto-reconnects on disconnect with
 * exponential backoff (5s -> 10s -> 20s -> 60s max).
 */

import { useState, useEffect, useRef, useCallback } from "react";

const SSE_URL = "/ai/api/events/stream";
const RECONNECT_BASE = 5000;    // 5 seconds initial
const RECONNECT_MAX  = 60000;   // 60 seconds cap

// Connection states: "connecting" | "connected" | "disconnected" | "error"

export default function useAIEvents(eventTypes = []) {
  const [connectionState, setConnectionState] = useState("disconnected");
  const [lastEvent, setLastEvent] = useState(null);
  const listenersRef = useRef({});
  const sourceRef = useRef(null);
  const reconnectTimer = useRef(null);
  const attemptRef = useRef(0);

  const connect = useCallback(() => {
    if (sourceRef.current) {
      sourceRef.current.close();
    }

    setConnectionState("connecting");
    const attempt = attemptRef.current;
    console.log(
      `[useAIEvents] Connecting to SSE (attempt ${attempt + 1})...`
    );

    const es = new EventSource(SSE_URL);
    sourceRef.current = es;

    es.onopen = () => {
      attemptRef.current = 0;          // reset backoff on success
      setConnectionState("connected");
      console.log("[useAIEvents] SSE connected");
    };

    es.onerror = () => {
      setConnectionState("error");
      es.close();

      // Exponential backoff: 5s, 10s, 20s, 40s, capped at 60s
      const delay = Math.min(
        RECONNECT_BASE * Math.pow(2, attemptRef.current),
        RECONNECT_MAX
      );
      attemptRef.current += 1;

      console.warn(
        `[useAIEvents] SSE disconnected — reconnecting in ${delay / 1000}s ` +
        `(attempt ${attemptRef.current})`
      );

      setConnectionState("disconnected");
      reconnectTimer.current = setTimeout(connect, delay);
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

  // Expose connectionState (connecting/connected/disconnected/error)
  // and `connected` boolean for backwards compatibility
  return { connected: connectionState === "connected", connectionState, lastEvent, on };
}
