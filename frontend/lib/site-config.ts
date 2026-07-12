export type Point = { x: number; y: number };
export type Obstacle = Point & { width: number; height: number; label: string };

// TODO: Replace this placeholder geometry with measured site coordinates.
export const SITE_GEOMETRY = {
  room: { width: 10, height: 10 },
  entrance: { x: 0.45, y: 8.8 },
  obstacles: [
    { x: 1.5, y: 1.0, width: 2.2, height: 1.15, label: "CELL 01" },
    { x: 5.1, y: 0.8, width: 2.8, height: 1.35, label: "CELL 02" },
    { x: 4.0, y: 4.1, width: 2.0, height: 1.4, label: "STORAGE" },
  ] satisfies Obstacle[],
  // TODO: Replace with the A* solver output in a later task.
  route: [
    { x: 0.45, y: 8.8 },
    { x: 2.3, y: 8.8 },
    { x: 2.3, y: 3.25 },
    { x: 7.8, y: 3.25 },
  ],
};
