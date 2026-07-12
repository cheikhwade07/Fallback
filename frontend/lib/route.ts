import { SITE_GEOMETRY, type Obstacle, type Point } from "./site-config";

export const CELL_SIZE = 0.05;
export const GRID_SIZE = Math.round((SITE_GEOMETRY.bounds.x1 - SITE_GEOMETRY.bounds.x0) / CELL_SIZE);
export const OBSTACLE_INFLATION = 0.15;

type Cell = { col: number; row: number };
export type RouteResult = { points: Point[]; direct: boolean; target: Point };

const directions = Array.from({ length: 3 }, (_, row) =>
  Array.from({ length: 3 }, (_, col) => ({ col: col - 1, row: row - 1 }))
).flat().filter(({ col, row }) => col !== 0 || row !== 0);
const key = (cell: Cell) => `${cell.col},${cell.row}`;
const distance = (a: Cell, b: Cell) => Math.hypot(a.col - b.col, a.row - b.row);
const same = (a: Cell, b: Cell) => a.col === b.col && a.row === b.row;

function toCell(point: Point): Cell {
  return { col: Math.max(0, Math.min(GRID_SIZE - 1, Math.floor((point.x - SITE_GEOMETRY.bounds.x0) / CELL_SIZE))), row: Math.max(0, Math.min(GRID_SIZE - 1, Math.floor((point.y - SITE_GEOMETRY.bounds.y0) / CELL_SIZE))) };
}
function toPoint(cell: Cell): Point { return { x: SITE_GEOMETRY.bounds.x0 + (cell.col + 0.5) * CELL_SIZE, y: SITE_GEOMETRY.bounds.y0 + (cell.row + 0.5) * CELL_SIZE }; }

function makeBlocked(obstacles: Obstacle[]): boolean[][] {
  return Array.from({ length: GRID_SIZE }, (_, row) => Array.from({ length: GRID_SIZE }, (_, col) => {
    const point = toPoint({ col, row });
    return obstacles.some((obstacle) => point.x >= obstacle.x0 - OBSTACLE_INFLATION && point.x <= obstacle.x1 + OBSTACLE_INFLATION && point.y >= obstacle.y0 - OBSTACLE_INFLATION && point.y <= obstacle.y1 + OBSTACLE_INFLATION);
  }));
}
function nearestFreeCell(origin: Cell, blocked: boolean[][]): Cell | null {
  let nearest: Cell | null = null; let nearestDistance = Infinity;
  for (let row = 0; row < GRID_SIZE; row += 1) for (let col = 0; col < GRID_SIZE; col += 1) if (!blocked[row][col]) {
    const candidate = { col, row }; const candidateDistance = distance(origin, candidate);
    if (candidateDistance < nearestDistance) { nearest = candidate; nearestDistance = candidateDistance; }
  }
  return nearest;
}
function canStep(from: Cell, to: Cell, blocked: boolean[][]): boolean {
  if (to.col < 0 || to.col >= GRID_SIZE || to.row < 0 || to.row >= GRID_SIZE || blocked[to.row][to.col]) return false;
  return from.col === to.col || from.row === to.row || (!blocked[from.row][to.col] && !blocked[to.row][from.col]);
}
function astar(start: Cell, goal: Cell, blocked: boolean[][]): Cell[] | null {
  const open = [start]; const cameFrom = new Map<string, Cell>();
  const gScore = new Map<string, number>([[key(start), 0]]); const fScore = new Map<string, number>([[key(start), distance(start, goal)]]);
  while (open.length) {
    let bestIndex = 0;
    for (let index = 1; index < open.length; index += 1) if ((fScore.get(key(open[index])) ?? Infinity) < (fScore.get(key(open[bestIndex])) ?? Infinity)) bestIndex = index;
    const current = open.splice(bestIndex, 1)[0];
    if (same(current, goal)) {
      const path = [current]; let previous = cameFrom.get(key(current));
      while (previous) { path.unshift(previous); previous = cameFrom.get(key(previous)); }
      return path;
    }
    for (const direction of directions) {
      const next = { col: current.col + direction.col, row: current.row + direction.row };
      if (!canStep(current, next, blocked)) continue;
      const nextKey = key(next); const tentative = (gScore.get(key(current)) ?? Infinity) + distance(current, next);
      if (tentative < (gScore.get(nextKey) ?? Infinity)) {
        cameFrom.set(nextKey, current); gScore.set(nextKey, tentative); fScore.set(nextKey, tentative + distance(next, goal));
        if (!open.some((cell) => same(cell, next))) open.push(next);
      }
    }
  }
  return null;
}
function smooth(cells: Cell[]): Cell[] {
  if (cells.length < 3) return cells;
  const result = [cells[0]];
  for (let index = 1; index < cells.length - 1; index += 1) {
    const before = cells[index - 1], current = cells[index], after = cells[index + 1];
    if ((current.col - before.col) * (after.row - current.row) !== (current.row - before.row) * (after.col - current.col)) result.push(current);
  }
  result.push(cells[cells.length - 1]); return result;
}
export function findRoute(entrance: Point, worker: Point, obstacles: Obstacle[]): RouteResult {
  const blocked = makeBlocked(obstacles); const start = nearestFreeCell(toCell(entrance), blocked); const target = nearestFreeCell(toCell(worker), blocked);
  if (!start || !target) return { points: [entrance], direct: true, target: entrance };
  const targetCell = toCell(worker); const workerIsValid = worker.x >= SITE_GEOMETRY.bounds.x0 && worker.x <= SITE_GEOMETRY.bounds.x1 && worker.y >= SITE_GEOMETRY.bounds.y0 && worker.y <= SITE_GEOMETRY.bounds.y1 && !blocked[targetCell.row][targetCell.col];
  const resolvedTarget = workerIsValid ? worker : toPoint(target); const cells = astar(start, target, blocked);
  if (!cells) return { points: [entrance, resolvedTarget], direct: true, target: resolvedTarget };
  return { points: [entrance, ...smooth(cells).slice(1).map(toPoint), resolvedTarget], direct: false, target: resolvedTarget };
}
