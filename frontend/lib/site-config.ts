export type Point = { x: number; y: number };
export type Obstacle = { x0: number; y0: number; x1: number; y1: number; label: string };

export const SITE_GEOMETRY = {
  bounds: { x0: 0.0, y0: 0.0, x1: 2.0, y1: 2.0 },
  entrance: { x: 2.0, y: 0.0 },
  obstacles: [
    { x0: 0.35, y0: 0.375, x1: 0.65, y1: 0.625, label: "BOX 01" },
    { x0: 1.35, y0: 1.375, x1: 1.65, y1: 1.625, label: "BOX 02" },
  ] satisfies Obstacle[],
};
