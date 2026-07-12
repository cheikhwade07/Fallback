"use client";

import { useState } from "react";
import type { Obstacle, Point } from "@/lib/site-config";

type Props = {
  obstacles: Obstacle[];
  entrance: Point;
  worker: Point;
  route: Point[];
  alertTone: "red" | "amber" | "neutral";
  initialView?: "2D" | "3D";
};

type ScreenPoint = { x: number; y: number };

const sx = (x: number) => 32 + x * 45;
const sy = (y: number) => 22 + y * 29;
const iso = (point: Point): ScreenPoint => ({
  x: 260 + (point.x - point.y) * 24,
  y: 60 + (point.x + point.y) * 13,
});

const points = (items: ScreenPoint[]) => items.map((point) => `${point.x},${point.y}`).join(" ");
const drop = (point: ScreenPoint, amount = 18): ScreenPoint => ({ x: point.x, y: point.y + amount });

function IsometricObstacle({ obstacle }: { obstacle: Obstacle }) {
  const top = [
    iso({ x: obstacle.x, y: obstacle.y }),
    iso({ x: obstacle.x + obstacle.width, y: obstacle.y }),
    iso({ x: obstacle.x + obstacle.width, y: obstacle.y + obstacle.height }),
    iso({ x: obstacle.x, y: obstacle.y + obstacle.height }),
  ];
  const right = [top[1], top[2], drop(top[2]), drop(top[1])];
  const front = [top[2], top[3], drop(top[3]), drop(top[2])];
  const label = iso({ x: obstacle.x + obstacle.width / 2, y: obstacle.y + obstacle.height / 2 });

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

export function SiteMap({ obstacles, entrance, worker, route, alertTone, initialView = "2D" }: Props) {
  const [view, setView] = useState<"2D" | "3D">(initialView);
  const fullRoute = [...route, worker];
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
              {[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => <line key={`v${n}`} x1={sx(n)} y1="15" x2={sx(n)} y2="325" />)}
              {[1, 2, 3, 4, 5, 6].map((n) => <line key={`h${n}`} x1="25" y1={sy(n)} x2="495" y2={sy(n)} />)}
            </g>
            {obstacles.map((obstacle) => {
              const x = sx(obstacle.x), y = sy(obstacle.y), w = obstacle.width * 45, h = obstacle.height * 29;
              return <g className="block" key={obstacle.label}><rect className="block-top" x={x} y={y} width={w} height={h} /><text className="block-label" x={x + w / 2} y={y + h / 2} textAnchor="middle" dominantBaseline="middle">{obstacle.label}</text></g>;
            })}
          </>
        ) : (
          <>
            <polygon className="room iso-floor" points={points([iso({ x: 0, y: 0 }), iso({ x: 10, y: 0 }), iso({ x: 10, y: 10 }), iso({ x: 0, y: 10 })])} />
            <g className="grid-lines iso-grid">
              {Array.from({ length: 9 }, (_, index) => index + 1).map((n) => <line key={`x${n}`} x1={iso({ x: n, y: 0 }).x} y1={iso({ x: n, y: 0 }).y} x2={iso({ x: n, y: 10 }).x} y2={iso({ x: n, y: 10 }).y} />)}
              {Array.from({ length: 9 }, (_, index) => index + 1).map((n) => <line key={`y${n}`} x1={iso({ x: 0, y: n }).x} y1={iso({ x: 0, y: n }).y} x2={iso({ x: 10, y: n }).x} y2={iso({ x: 10, y: n }).y} />)}
            </g>
            {obstacles.map((obstacle) => <IsometricObstacle obstacle={obstacle} key={obstacle.label} />)}
          </>
        )}
        <polyline className="route" points={points(routePoints)} />
        <g className="entrance" transform={`translate(${project(entrance).x} ${project(entrance).y})`}><rect x="-8" y="-8" width="16" height="16" /><text x="14" y="4">ENTRY</text></g>
        <g className="worker" style={{ color: workerAccent }} transform={`translate(${project(worker).x} ${project(worker).y})`}>
          <circle className="worker-pulse" r="14" /><circle r="6" /><text x="13" y="4">WORKER</text>
        </g>
      </svg>
      <div className="map-legend"><span>ZONE B // 10 × 10 M</span><span>ROUTE {fullRoute.length} PTS</span></div>
    </div>
  );
}
