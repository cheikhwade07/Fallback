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
const obstacleDisplayLabel = (label: string) => label.replace(/^BOX\b/, "OBSTACLE");

function PlanObstacle({ obstacle, index }: { obstacle: Obstacle; index: number }) {
  const x = sx(obstacle.x0), y = sy(obstacle.y0), w = sx(obstacle.x1) - sx(obstacle.x0), h = sy(obstacle.y1) - sy(obstacle.y0);
  const depth = 7;
  const label = obstacleDisplayLabel(obstacle.label);

  return (
    <g className="block" key={obstacle.label}>
      <rect className="ground-shadow" x={x + 7} y={y + 10} width={w} height={h} rx="1" />
      <polygon className="block-depth" points={points([{ x, y }, { x: x + w, y }, { x: x + w + depth, y: y + depth }, { x: x + w + depth, y: y + h + depth }, { x: x + depth, y: y + h + depth }, { x, y: y + h }])} />
      <rect className="block-top" x={x} y={y} width={w} height={h} rx="1" />
      <line className="block-edge-highlight" x1={x + 1} y1={y + 1} x2={x + w - 1} y2={y + 1} />
      <text className="block-label" x={x + w / 2} y={y + h / 2} textAnchor="middle" dominantBaseline="middle">{label || `OBSTACLE ${String(index + 1).padStart(2, "0")}`}</text>
    </g>
  );
}

function PlanWalls() {
  const x0 = sx(SITE_GEOMETRY.bounds.x0), x1 = sx(SITE_GEOMETRY.bounds.x1);
  const y0 = sy(SITE_GEOMETRY.bounds.y0), y1 = sy(SITE_GEOMETRY.bounds.y1);
  const wall = 9;
  const doorGap = 32;

  return (
    <g className="room-walls" aria-hidden="true">
      <rect className="room-wall" x={x0} y={y0} width={x1 - x0 - doorGap} height={wall} />
      <rect className="room-wall" x={x0} y={y0} width={wall} height={y1 - y0} />
      <rect className="room-wall" x={x0} y={y1 - wall} width={x1 - x0} height={wall} />
      <path className="room-wall-highlight" d={`M${x0 + 1},${y0 + 1}H${x1 - doorGap - 1} M${x0 + 1},${y0 + 1}V${y1 - 1} M${x0 + 1},${y1 - 1}H${x1 - 1}`} />
    </g>
  );
}

function IsoWall({ from, to }: { from: ScreenPoint; to: ScreenPoint }) {
  const lowFrom = drop(from, 11), lowTo = drop(to, 11);
  return <polygon className="room-wall-iso" points={points([from, to, lowTo, lowFrom])} />;
}

function IsometricWalls() {
  return (
    <g className="room-walls" aria-hidden="true">
      <IsoWall from={iso({ x: SITE_GEOMETRY.bounds.x0, y: SITE_GEOMETRY.bounds.y0 })} to={iso({ x: 1.82, y: SITE_GEOMETRY.bounds.y0 })} />
      <IsoWall from={iso({ x: SITE_GEOMETRY.bounds.x0, y: SITE_GEOMETRY.bounds.y1 })} to={iso({ x: SITE_GEOMETRY.bounds.x0, y: SITE_GEOMETRY.bounds.y0 })} />
      <IsoWall from={iso({ x: SITE_GEOMETRY.bounds.x1, y: SITE_GEOMETRY.bounds.y1 })} to={iso({ x: SITE_GEOMETRY.bounds.x0, y: SITE_GEOMETRY.bounds.y1 })} />
    </g>
  );
}

function EntranceDoor({ point, view }: { point: ScreenPoint; view: "2D" | "3D" }) {
  return (
    <g className={`entrance entrance-${view.toLowerCase()}`} transform={`translate(${point.x} ${point.y})`}>
      {view === "2D" ? (
        <>
          <path className="door-frame" d="M-32,0V25 M0,0V25" />
          <path className="door-threshold" d="M-32,0H0" />
          <path className="door-leaf" d="M-32,0A32,32 0 0 1 0,32" />
          <text className="entrance-label" x="-34" y="-7" textAnchor="end">ENTRY</text>
        </>
      ) : (
        <>
          <path className="door-frame" d="M-28,-14L0,0 M-28,14L0,0" />
          <path className="door-threshold" d="M-28,0H0" />
          <path className="door-leaf" d="M-28,-14A28,28 0 0 0 -28,14" />
          <text className="entrance-label" x="12" y="4">ENTRY</text>
        </>
      )}
    </g>
  );
}

function IsometricObstacle({ obstacle, index }: { obstacle: Obstacle; index: number }) {
  const top = [
    iso({ x: obstacle.x0, y: obstacle.y0 }),
    iso({ x: obstacle.x1, y: obstacle.y0 }),
    iso({ x: obstacle.x1, y: obstacle.y1 }),
    iso({ x: obstacle.x0, y: obstacle.y1 }),
  ];
  const right = [top[1], top[2], drop(top[2]), drop(top[1])];
  const front = [top[2], top[3], drop(top[3]), drop(top[2])];
  const label = iso({ x: (obstacle.x0 + obstacle.x1) / 2, y: (obstacle.y0 + obstacle.y1) / 2 });
  const displayLabel = obstacleDisplayLabel(obstacle.label) || `OBSTACLE ${String(index + 1).padStart(2, "0")}`;

  return (
    <g className="block" key={obstacle.label}>
      <polygon className="ground-shadow" points={points(top.map((point) => ({ x: point.x + 8, y: point.y + 18 })))} />
      <polygon className="block-side" points={points(right)} />
      <polygon className="block-front" points={points(front)} />
      <polygon className="block-top" points={points(top)} />
      <polyline className="block-edge-highlight" points={points([...top, top[0]])} />
      <text className="block-label" x={label.x} y={label.y} textAnchor="middle" dominantBaseline="middle">{displayLabel}</text>
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
        <defs>
          <marker id="route-arrow" viewBox="-2 -5 12 10" refX="9" refY="0" markerWidth="7" markerHeight="7" markerUnits="userSpaceOnUse" orient="auto">
            <path className="route-arrow" d="M0,-4L10,0L0,4Z" />
          </marker>
        </defs>
        {view === "2D" ? (
          <>
            <rect className="room room-floor" x="25" y="15" width="470" height="310" />
            <g className="grid-lines">
              {[0.5, 1, 1.5].map((n) => <line key={`v${n}`} x1={sx(n)} y1="15" x2={sx(n)} y2="325" />)}
              {[0.5, 1, 1.5].map((n) => <line key={`h${n}`} x1="25" y1={sy(n)} x2="495" y2={sy(n)} />)}
            </g>
            <PlanWalls />
            {obstacles.map((obstacle, index) => <PlanObstacle obstacle={obstacle} index={index} key={obstacle.label} />)}
          </>
        ) : (
          <>
            <polygon className="room iso-floor" points={points([iso({ x: SITE_GEOMETRY.bounds.x0, y: SITE_GEOMETRY.bounds.y0 }), iso({ x: SITE_GEOMETRY.bounds.x1, y: SITE_GEOMETRY.bounds.y0 }), iso({ x: SITE_GEOMETRY.bounds.x1, y: SITE_GEOMETRY.bounds.y1 }), iso({ x: SITE_GEOMETRY.bounds.x0, y: SITE_GEOMETRY.bounds.y1 })])} />
            <g className="grid-lines iso-grid">
              {[0.5, 1, 1.5].map((n) => <line key={`x${n}`} x1={iso({ x: n, y: SITE_GEOMETRY.bounds.y0 }).x} y1={iso({ x: n, y: SITE_GEOMETRY.bounds.y0 }).y} x2={iso({ x: n, y: SITE_GEOMETRY.bounds.y1 }).x} y2={iso({ x: n, y: SITE_GEOMETRY.bounds.y1 }).y} />)}
              {[0.5, 1, 1.5].map((n) => <line key={`y${n}`} x1={iso({ x: SITE_GEOMETRY.bounds.x0, y: n }).x} y1={iso({ x: SITE_GEOMETRY.bounds.x0, y: n }).y} x2={iso({ x: SITE_GEOMETRY.bounds.x1, y: n }).x} y2={iso({ x: SITE_GEOMETRY.bounds.x1, y: n }).y} />)}
            </g>
            <IsometricWalls />
            {obstacles.map((obstacle, index) => <IsometricObstacle obstacle={obstacle} index={index} key={obstacle.label} />)}
          </>
        )}
        <polyline className="route route-halo" points={points(routePoints)} aria-hidden="true" />
        <polyline className={`route${routeResult.direct ? " route-direct" : ""}`} points={points(routePoints)} markerEnd="url(#route-arrow)" />
        {routeResult.direct && <text className="route-label" x={260} y={338}>DIRECT LINE // NO CLEAR ROUTE</text>}
        <EntranceDoor point={project(entrance)} view={view} />
        <g className="worker" style={{ color: workerAccent }} transform={`translate(${project(resolvedWorker).x} ${project(resolvedWorker).y})`}>
          <circle className="worker-pulse" r="17" /><circle className="worker-ring" r="11" /><circle className="worker-core" r="8" /><text x="15" y="4">WORKER</text>
        </g>
      </svg>
      <div className="map-legend"><span>ZONE B // 2 × 2 M</span><span>{routeResult.direct ? "DIRECT LINE" : `ROUTE ${fullRoute.length} PTS`}</span></div>
    </div>
  );
}
