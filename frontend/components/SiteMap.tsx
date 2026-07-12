"use client";

import { useState } from "react";
import { SITE_GEOMETRY, type Obstacle, type Point } from "@/lib/site-config";
import { findRoute } from "@/lib/route";

type Props = {
  obstacles: Obstacle[];
  entrance: Point;
  worker: Point;
  alertTone: "red" | "amber" | "neutral";
  initialView?: "2D" | "3D";
};

type ScreenPoint = { x: number; y: number };

const sx = (x: number) => 25 + ((x - SITE_GEOMETRY.bounds.x0) / (SITE_GEOMETRY.bounds.x1 - SITE_GEOMETRY.bounds.x0)) * 470;
const sy = (y: number) => 15 + ((y - SITE_GEOMETRY.bounds.y0) / (SITE_GEOMETRY.bounds.y1 - SITE_GEOMETRY.bounds.y0)) * 310;
const iso = (point: Point): ScreenPoint => ({
  x: 260 + (point.x - point.y) * 100,
  y: 60 + (point.x + point.y) * 55,
});

const points = (items: ScreenPoint[]) => items.map((point) => `${point.x},${point.y}`).join(" ");
const drop = (point: ScreenPoint, amount = 18): ScreenPoint => ({ x: point.x, y: point.y + amount });

function IsometricObstacle({ obstacle }: { obstacle: Obstacle }) {
  const top = [
    iso({ x: obstacle.x0, y: obstacle.y0 }),
    iso({ x: obstacle.x1, y: obstacle.y0 }),
    iso({ x: obstacle.x1, y: obstacle.y1 }),
    iso({ x: obstacle.x0, y: obstacle.y1 }),
  ];
  const right = [top[1], top[2], drop(top[2]), drop(top[1])];
  const front = [top[2], top[3], drop(top[3]), drop(top[2])];
  const label = iso({ x: (obstacle.x0 + obstacle.x1) / 2, y: (obstacle.y0 + obstacle.y1) / 2 });

  return (
    <g className="block" key={obstacle.label}>
      <polygon className="ground-shadow" points={points(top.map((point) => ({ x: point.x + 7, y: point.y + 14 })))} />
      <polygon className="block-side" points={points(right)} />
      <polygon className="block-front" points={points(front)} />
      <polygon className="block-top" points={points(top)} />
      <text className="block-label" x={label.x} y={label.y} textAnchor="middle" dominantBaseline="middle">{obstacle.label}</text>
    </g>
  );
}

export function SiteMap({ obstacles, entrance, worker, alertTone, initialView = "2D" }: Props) {
  const [view, setView] = useState<"2D" | "3D">(initialView);
  const routeResult = findRoute(entrance, worker, obstacles);
  const resolvedWorker = routeResult.target;
  const fullRoute = routeResult.points;
  const workerAccent = alertTone === "red" ? "#b93832" : alertTone === "amber" ? "#ffb52e" : "#aeb2ae";
  const project = view === "3D" ? iso : (point: Point) => ({ x: sx(point.x), y: sy(point.y) });
  const routePoints = fullRoute.map(project);

  return (
    <div className={`map-wrap map-${view.toLowerCase()}`}>
      <div className="map-toggle" aria-label="Map view">
        {(["2D", "3D"] as const).map((item) => (
          <button type="button" aria-pressed={view === item} className={view === item ? "active" : ""} key={item} onClick={() => setView(item)}>{item}</button>
        ))}
      </div>
      <svg className={`site-map route-${alertTone}`} viewBox="0 0 520 350" role="img" aria-label={`${view} responder route map`}>
        {view === "2D" ? (
          <>
            <rect className="room" x="25" y="15" width="470" height="310" />
            <g className="grid-lines">
              {[0.5, 1, 1.5].map((n) => <line key={`v${n}`} x1={sx(n)} y1="15" x2={sx(n)} y2="325" />)}
              {[0.5, 1, 1.5].map((n) => <line key={`h${n}`} x1="25" y1={sy(n)} x2="495" y2={sy(n)} />)}
            </g>
            {obstacles.map((obstacle) => {
              const x = sx(obstacle.x0), y = sy(obstacle.y0), w = sx(obstacle.x1) - sx(obstacle.x0), h = sy(obstacle.y1) - sy(obstacle.y0);
              return <g className="block" key={obstacle.label}><rect className="block-top" x={x} y={y} width={w} height={h} /><text className="block-label" x={x + w / 2} y={y + h / 2} textAnchor="middle" dominantBaseline="middle">{obstacle.label}</text></g>;
            })}
          </>
        ) : (
          <>
            <polygon className="room iso-floor" points={points([iso({ x: SITE_GEOMETRY.bounds.x0, y: SITE_GEOMETRY.bounds.y0 }), iso({ x: SITE_GEOMETRY.bounds.x1, y: SITE_GEOMETRY.bounds.y0 }), iso({ x: SITE_GEOMETRY.bounds.x1, y: SITE_GEOMETRY.bounds.y1 }), iso({ x: SITE_GEOMETRY.bounds.x0, y: SITE_GEOMETRY.bounds.y1 })])} />
            <g className="grid-lines iso-grid">
              {[0.5, 1, 1.5].map((n) => <line key={`x${n}`} x1={iso({ x: n, y: SITE_GEOMETRY.bounds.y0 }).x} y1={iso({ x: n, y: SITE_GEOMETRY.bounds.y0 }).y} x2={iso({ x: n, y: SITE_GEOMETRY.bounds.y1 }).x} y2={iso({ x: n, y: SITE_GEOMETRY.bounds.y1 }).y} />)}
              {[0.5, 1, 1.5].map((n) => <line key={`y${n}`} x1={iso({ x: SITE_GEOMETRY.bounds.x0, y: n }).x} y1={iso({ x: SITE_GEOMETRY.bounds.x0, y: n }).y} x2={iso({ x: SITE_GEOMETRY.bounds.x1, y: n }).x} y2={iso({ x: SITE_GEOMETRY.bounds.x1, y: n }).y} />)}
            </g>
            {obstacles.map((obstacle) => <IsometricObstacle obstacle={obstacle} key={obstacle.label} />)}
          </>
        )}
        <polyline className={`route${routeResult.direct ? " route-direct" : ""}`} points={points(routePoints)} />
        {routeResult.direct && <text className="route-label" x={260} y={338}>DIRECT LINE // NO CLEAR ROUTE</text>}
        <g className="entrance" transform={`translate(${project(entrance).x} ${project(entrance).y})`}><rect x="-8" y="-8" width="16" height="16" /><text x="14" y="4">ENTRY</text></g>
        <g className="worker" style={{ color: workerAccent }} transform={`translate(${project(resolvedWorker).x} ${project(resolvedWorker).y})`}>
          <circle className="worker-pulse" r="14" /><circle r="6" /><text x="13" y="4">WORKER</text>
        </g>
      </svg>
      <div className="map-legend"><span>ZONE B // 2 × 2 M</span><span>{routeResult.direct ? "DIRECT LINE" : `ROUTE ${fullRoute.length} PTS`}</span></div>
    </div>
  );
}
