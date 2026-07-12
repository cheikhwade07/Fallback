"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

export type EventType = "FALL_DETECTED" | "HEARTBEAT" | "RECOVERED";
export type StreamEvent = {
  node_id: string;
  event_type: EventType;
  x: number;
  y: number;
  fall_duration: number;
  latency_ms: number;
  timestamp: string;
  frame_b64: string;
  briefing?: string;
  briefing_source?: "gemini" | "fallback";
};
export type UiState = "IDLE" | "DOWN" | "FALL_CONFIRMED";
export type PreviewMode = "LIVE" | UiState;

const configuredApiBase = process.env.NEXT_PUBLIC_API_BASE;
const API_BASE = configuredApiBase === undefined
  ? (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "")
  : configuredApiBase;
const STREAM_URL = `${API_BASE}/api/stream`;

const PREVIEW_EVENTS: Record<UiState, StreamEvent> = {
  IDLE: {
    node_id: "preview-node",
    event_type: "RECOVERED",
    x: 0.25,
    y: 0.25,
    fall_duration: 0,
    latency_ms: 88,
    timestamp: "2026-01-01T00:00:00.000Z",
    frame_b64: "",
  },
  DOWN: {
    node_id: "preview-node",
    event_type: "HEARTBEAT",
    x: 1.75,
    y: 0.25,
    fall_duration: 2.4,
    latency_ms: 91,
    timestamp: "2026-01-01T00:00:02.400Z",
    frame_b64: "",
  },
  FALL_CONFIRMED: {
    node_id: "preview-node",
    event_type: "FALL_DETECTED",
    x: 0.25,
    y: 1.75,
    fall_duration: 7.4,
    latency_ms: 107,
    timestamp: "2026-01-01T00:00:07.400Z",
    frame_b64: "",
  },
};

export function useLiveStream() {
  const [lastEvent, setLastEvent] = useState<StreamEvent | null>(null);
  const [alertEvent, setAlertEvent] = useState<StreamEvent | null>(null);
  const [recoveredEvent, setRecoveredEvent] = useState<StreamEvent | null>(null);
  const [latchedFall, setLatchedFall] = useState(false);
  const [previewMode, setPreviewMode] = useState<PreviewMode>("LIVE");

  useEffect(() => {
    const stream = new EventSource(STREAM_URL);
    stream.onmessage = (message) => {
      try {
        const event = JSON.parse(message.data) as StreamEvent;
        setLastEvent(event);
        setPreviewMode("LIVE");
        if (event.event_type === "FALL_DETECTED") {
          setAlertEvent(event);
          setRecoveredEvent(null);
          setLatchedFall(true);
        } else if (event.event_type === "RECOVERED") {
          setRecoveredEvent(event);
        }
      } catch {
        // Ignore malformed stream messages and keep the last valid state.
      }
    };
    return () => stream.close();
  }, []);

  const acknowledge = useCallback(() => {
    setLatchedFall(false);
    setPreviewMode("LIVE");
  }, []);

  const state: UiState = previewMode === "LIVE"
    ? (latchedFall ? "FALL_CONFIRMED" : "IDLE")
    : previewMode;
  const event = previewMode === "LIVE"
    ? (latchedFall ? alertEvent ?? lastEvent : lastEvent)
    : PREVIEW_EVENTS[previewMode];

  return useMemo(() => ({
    event,
    lastEvent,
    recoveredEvent,
    acknowledge,
    liveState: latchedFall ? "FALL_CONFIRMED" as UiState : "IDLE" as UiState,
    previewMode,
    setPreviewMode,
    state,
  }), [acknowledge, event, lastEvent, latchedFall, previewMode, recoveredEvent, state]);
}
