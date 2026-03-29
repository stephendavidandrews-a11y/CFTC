/**
 * WebSocket hook for real-time capture (ReSpeaker Pi) status.
 *
 * Fetches a WS auth token via /tracker/api/capture/ws-token, then
 * connects to /tracker/ws/capture-status for live status updates.
 * Auto-reconnects with exponential backoff (5s → 60s cap).
 *
 * Browser notifications on offline/error transitions (requires permission).
 *
 * Returns:
 *   status      — latest normalized status_update from backend (or null)
 *   thresholds  — server-sent threshold constants from welcome message
 *   connectionState — "connecting" | "connected" | "disconnected" | "error"
 *   connected   — boolean shorthand
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { fetchJSON } from "../api/client";

const RECONNECT_BASE = 5000; // 5 seconds
const RECONNECT_MAX = 60000; // 60 seconds cap

// States that trigger a browser notification when entered
const ALERT_STATES = new Set(["offline", "error"]);

function notifyStateChange(newState, prevState) {
  if (!ALERT_STATES.has(newState)) return;
  if (prevState === newState) return; // no transition
  if (typeof Notification === "undefined") return;
  if (Notification.permission !== "granted") return;

  const title = newState === "error"
    ? "Capture Error"
    : "Capture Offline";
  const body = newState === "error"
    ? "ReSpeaker Pi reported an error"
    : "ReSpeaker Pi heartbeat lost";

  try {
    new Notification(title, {
      body: body,
      icon: "/favicon.ico",
      tag: "capture-status", // replaces previous notification
    });
  } catch {
    // Notification constructor can throw in some contexts
  }
}

export default function useCaptureStatus() {
  const [status, setStatus] = useState(null);
  const [thresholds, setThresholds] = useState(null);
  const [connectionState, setConnectionState] = useState("disconnected");

  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);
  const attemptRef = useRef(0);
  const tokenRef = useRef(null);
  const mountedRef = useRef(true);
  const prevStateRef = useRef(null);

  // Request notification permission once on mount
  useEffect(() => {
    if (typeof Notification !== "undefined" && Notification.permission === "default") {
      Notification.requestPermission();
    }
  }, []);

  const fetchToken = useCallback(async () => {
    try {
      const data = await fetchJSON("/tracker/api/capture/ws-token");
      return data.token;
    } catch (err) {
      console.warn("[useCaptureStatus] Failed to fetch WS token:", err.message);
      return null;
    }
  }, []);

  const connect = useCallback(async () => {
    if (!mountedRef.current) return;

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setConnectionState("connecting");

    // Get token if we don't have one (or on first connect)
    if (!tokenRef.current) {
      tokenRef.current = await fetchToken();
      if (!tokenRef.current) {
        setConnectionState("error");
        // Retry with backoff
        const delay = Math.min(
          RECONNECT_BASE * Math.pow(2, attemptRef.current),
          RECONNECT_MAX
        );
        attemptRef.current += 1;
        console.warn(
          "[useCaptureStatus] No token \u2014 retrying in " + (delay / 1000) + "s"
        );
        reconnectTimer.current = setTimeout(connect, delay);
        return;
      }
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const wsUrl = protocol + "//" + window.location.host + "/tracker/ws/capture-status?token=" + tokenRef.current;

    console.log(
      "[useCaptureStatus] Connecting (attempt " + (attemptRef.current + 1) + ")..."
    );

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      attemptRef.current = 0;
      setConnectionState("connected");
      console.log("[useCaptureStatus] WebSocket connected");
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      try {
        const msg = JSON.parse(event.data);

        if (msg.type === "welcome") {
          if (msg.thresholds) setThresholds(msg.thresholds);
          if (msg.last_status) {
            setStatus(msg.last_status);
            prevStateRef.current = msg.last_status.state || null;
          }
        } else if (msg.type === "status_update") {
          const newState = msg.state || "offline";
          notifyStateChange(newState, prevStateRef.current);
          prevStateRef.current = newState;
          setStatus(msg);
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = (event) => {
      if (!mountedRef.current) return;

      // If closed with 1008 (Unauthorized), token may be stale — clear it
      if (event.code === 1008) {
        tokenRef.current = null;
        console.warn("[useCaptureStatus] Token rejected \u2014 will re-fetch");
      }

      const delay = Math.min(
        RECONNECT_BASE * Math.pow(2, attemptRef.current),
        RECONNECT_MAX
      );
      attemptRef.current += 1;
      setConnectionState("disconnected");
      console.warn(
        "[useCaptureStatus] Disconnected \u2014 reconnecting in " + (delay / 1000) + "s " +
          "(attempt " + attemptRef.current + ")"
      );
      reconnectTimer.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      // onclose will fire after onerror — let onclose handle reconnect
      if (mountedRef.current) setConnectionState("error");
    };
  }, [fetchToken]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, [connect]);

  return {
    status,
    thresholds,
    connectionState,
    connected: connectionState === "connected",
  };
}
