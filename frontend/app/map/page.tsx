"use client";

import { SITE_GEOMETRY } from "@/lib/site-config";
import { useLiveStream } from "@/lib/live-stream";
import { DevStateBar } from "@/components/Dashboard";
import { SiteMap } from "@/components/SiteMap";

export default function MapPage() {
  const { event, previewMode, setPreviewMode, state } = useLiveStream();
  const worker = { x: event?.x ?? 1.75, y: event?.y ?? 1.75 };
  const tone = state === "FALL_CONFIRMED" ? "red" : state === "DOWN" ? "amber" : "neutral";
  const stateLabel = state === "FALL_CONFIRMED" ? "MAN DOWN" : state === "DOWN" ? "POSTURE DOWN" : "ALL CLEAR";

  return <main className={`map-page state-${state.toLowerCase()}`}>
    <header className="map-page-header"><a href="/">FALLBACK</a><span>/ RESPONDER ROUTE / LEVEL 01</span><strong>{stateLabel}</strong><small>{event ? `NODE ${event.node_id} · X ${worker.x.toFixed(1)} / Y ${worker.y.toFixed(1)} M` : "WAITING FOR LIVE EVENT"}</small></header>
    <section className="full-map-panel">
      <header><span>RESPONDER ROUTE / {state === "FALL_CONFIRMED" ? "FALL CONFIRMED" : "LIVE"}</span><span>2D / 3D MAP</span></header>
      <SiteMap obstacles={SITE_GEOMETRY.obstacles} entrance={SITE_GEOMETRY.entrance} worker={worker} alertTone={tone}/>
    </section>
    <DevStateBar mode={previewMode} onChange={setPreviewMode}/>
  </main>;
}
