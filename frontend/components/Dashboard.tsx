"use client";

import type { ReactNode } from "react";
import { SITE_GEOMETRY } from "@/lib/site-config";
import { useLiveStream, type PreviewMode, type StreamEvent, type UiState } from "@/lib/live-stream";
import { SiteMap } from "./SiteMap";

const BRIEFING = "Node {node} detected sustained prone posture for 3.0 seconds. Safety output has fired and the responder route is projected to the confirmed event position.";

const clock = (seconds: number) => `${String(Math.floor(Math.max(0, seconds) / 60)).padStart(2, "0")}:${String(Math.floor(Math.max(0, seconds) % 60)).padStart(2, "0")}`;
const time = (value?: string) => {
  const date = value ? new Date(value) : null;
  return date && !Number.isNaN(date.valueOf()) ? date.toISOString().slice(11, 23) : "--:--:--.---";
};

export function Panel({ title, meta, className = "", actions, children }: { title: string; meta: string; className?: string; actions?: ReactNode; children: ReactNode }) {
  return <section className={`fig-panel ${className}`}><header><span>{title}</span>{actions}<span>{meta}</span></header><div className="fig-panel-body">{children}</div></section>;
}

function Skeleton({ fallen = false }: { fallen?: boolean }) {
  return <svg className={`fig-skeleton ${fallen ? "fallen" : "upright"}`} viewBox="0 0 360 155" aria-hidden="true">
    {fallen ? <><rect x="1" y="1" width="358" height="153"/><g><circle cx="225" cy="28" r="8"/><circle cx="45" cy="90" r="5"/><circle cx="115" cy="86" r="5"/><circle cx="175" cy="60" r="5"/><circle cx="245" cy="88" r="5"/><circle cx="320" cy="92" r="5"/><circle cx="182" cy="120" r="5"/><circle cx="120" cy="140" r="5"/><circle cx="255" cy="140" r="5"/><path d="M45 90L115 86L175 60L225 28M175 60L182 120M175 60L245 88L320 92M182 120L120 140M182 120L255 140"/></g></> : <g><circle cx="180" cy="28" r="10"/><path d="M180 0V28M150 42L180 72L210 42M158 60L180 112L202 60"/></g>}
  </svg>;
}

function Camera({ image, state }: { image: string | null; state: UiState }) {
  return <div className={`camera camera-${state.toLowerCase()}`}>
    {image ? <img className="live-frame" src={image} alt="Latest annotated detection frame" /> : <div className="mock-scene"><i className="column one"/><i className="column two"/><i className="floor"/></div>}
    <Skeleton fallen={state !== "IDLE"}/>
    <footer>{state === "IDLE" ? "LIVE FRAME · MONITORING" : state === "DOWN" ? "POSTURE DOWN · PREVIEW" : "EVENT FRAME · FROZEN AT DETECTION"}</footer>
  </div>;
}

function AlertBand({ state, duration, recoveredEvent, onAcknowledge }: { state: UiState; duration: number; recoveredEvent: StreamEvent | null; onAcknowledge: () => void }) {
  const down = state === "DOWN";
  const idle = state === "IDLE";
  return <section className="fig-alert">
    <div className="alert-main"><span>{idle ? "SITE CLEAR // ZONE B" : down ? "POSTURE DOWN" : "FALL CONFIRMED // ZONE B"}</span><h1>{idle ? "ALL CLEAR" : down ? "CONFIRMING" : "MAN DOWN"}</h1><small>FALL DURATION {duration.toFixed(1).padStart(4, "0")} S</small></div>
    <div className="alert-evidence"><span>CONFIRMATION EVIDENCE</span><b className={idle ? "" : "checked"}>HORIZONTAL POSTURE</b><b className={!down && !idle ? "checked" : ""}>3.0 S THRESHOLD</b></div>
    <div className="alert-clock"><div>DOWN {clock(duration)}</div><small>SAFETY OUTPUT {idle || down ? "ARMED" : "FIRED"}</small>{down && <i><b style={{ width: `${Math.min(100, duration / 3 * 100)}%` }}/></i>}{state === "FALL_CONFIRMED" && <button type="button" className="acknowledge" onClick={onAcknowledge}>ACKNOWLEDGE</button>}</div>
    {recoveredEvent && <div className="alert-event-log">EVENT LOG // RECOVERED {time(recoveredEvent.timestamp)}{state === "FALL_CONFIRMED" ? " // ALERT LATCH HELD" : ""}</div>}
  </section>;
}

export function DevStateBar({ mode, onChange }: { mode: PreviewMode; onChange: (mode: PreviewMode) => void }) {
  return <div className={`dev-override ${mode !== "LIVE" ? "is-preview" : ""}`} aria-label="Development state preview">
    <span>{mode === "LIVE" ? "LIVE" : "PREVIEW"}</span>
    {(["IDLE", "DOWN", "FALL_CONFIRMED", "LIVE"] as const).map((item) => <button type="button" key={item} className={mode === item ? "active" : ""} aria-pressed={mode === item} onClick={() => onChange(item)}>{item}</button>)}
  </div>;
}

export function Dashboard() {
  const { acknowledge, event, previewMode, recoveredEvent, setPreviewMode, state } = useLiveStream();
  const duration = state === "IDLE" ? 0 : event?.fall_duration ?? 0;
  const worker = { x: event?.x ?? 7.8, y: event?.y ?? 3.25 };
  const image = event?.frame_b64 ? `data:image/jpeg;base64,${event.frame_b64}` : null;
  const node = event?.node_id ?? "--";
  const status = state === "IDLE" ? "MONITORING" : state === "DOWN" ? "POSTURE DOWN" : "FALL CONFIRMED";
  const alertTone = state === "FALL_CONFIRMED" ? "red" : state === "DOWN" ? "amber" : "neutral";

  return <main className={`fig-dashboard state-${state.toLowerCase()}`}>
    <header className="fig-header"><strong>FALLBACK</strong><span>// SITE 04</span><i/><b>NODE {node}</b><em><i/>{status}</em><small>{state === "IDLE" ? `LATENCY_MS ${event ? Math.round(event.latency_ms) : "--"}` : `EVENT TIMESTAMP ${time(event?.timestamp)}    LATENCY_MS ${event ? String(Math.round(event.latency_ms)).padStart(3, "0") : "--"}`}</small></header>
    <div className={`state-layout ${state.toLowerCase()}-layout`}>
      <div className="layout-left">
        <AlertBand state={state} duration={duration} recoveredEvent={recoveredEvent} onAcknowledge={acknowledge}/>
        <Panel title={state === "DOWN" ? "LIVE FRAME" : "LAST FRAME"} meta={state === "IDLE" ? "LIVE / CAM 01" : time(event?.timestamp)} className={`${state.toLowerCase()}-frame`}><Camera image={image} state={state}/></Panel>
      </div>
      <div className="layout-right">
        <Panel title="SITE MAP" meta="2D · 2 M GRID" className={`${state.toLowerCase()}-map`} actions={<a className="expand-map" href="/map">EXPAND</a>}><SiteMap obstacles={SITE_GEOMETRY.obstacles} entrance={SITE_GEOMETRY.entrance} worker={worker} route={SITE_GEOMETRY.route} alertTone={alertTone}/></Panel>
        {state === "IDLE" ? <Panel title="OPERATIONAL BRIEFING" meta="SYSTEM NOMINAL" className="idle-brief layout-brief"><div className="idle-copy"><h2>NODE {node} / FALLBACK MONITORING</h2><p>Depth and pose streams are nominal.<br/>The responder route remains staged while<br/>posture is upright.</p><div className="briefing-facts"><span>POSTURE&nbsp; UPRIGHT</span><span>EVENT STATE&nbsp; IDLE</span><span>FALL TIMER&nbsp; 00:00</span><span>GPIO&nbsp; ARMED / NOT FIRED</span></div></div></Panel> : state === "DOWN" ? <Panel title="OPERATIONAL BRIEFING" meta="SAFETY HOLD" className="down-state layout-brief"><div className="down-copy"><h2>FALL NOT YET CONFIRMED</h2><p>Awaiting sustained down duration of 3.0 seconds.</p><div><span>POSTURE<b>DOWN</b></span><span>DOWN_DURATION_S<b>{duration.toFixed(1)}</b></span><span>CONFIRM_THRESHOLD_S<b>03.0</b></span><span>SAFETY OUTPUT<b>HOLD</b></span></div></div></Panel> : <Panel title="OPERATIONAL BRIEFING" meta="BRIEFING ACTIVE" className="confirmed-brief layout-brief"><div className="confirmed-copy"><p>{BRIEFING.replace("{node}", node)}</p><div className="briefing-facts"><span>EVENT ID / FALL-2407-091</span><span>ZONE / LEVEL 01 · EAST BAY</span><span>OUTPUT / GPIO 17 · FIRED</span></div></div></Panel>}
      </div>
    </div>
    <DevStateBar mode={previewMode} onChange={setPreviewMode}/>
  </main>;
}
