// toplevel.ts — фиктивные данные для теста .0 (TypeScript)

import { readFile } from "fs";
import type { Box } from "./box";

export { Apple } from "./apple";
export { Pear, Plum } from "./fruit";

export const MAX_BOXES = 12;
export const CONFIG = {
  size: "L",
  tags: ["fresh", "ripe"],
  nested: { cold: true, shelf: 3 },
};

export type BoxId = string | number;

export interface Table {
  id: BoxId;
  boxes: Box[];
}

export enum Color {
  Red,
  Green,
  Blue,
}

export function pack(box: Box): Table {
  return { id: 1, boxes: [box] };
}

export class Warehouse {
  private tables: Table[] = [];

  add(t: Table): void {
    this.tables.push(t);
  }
}

namespace legacy {
  export const OLD = 1;
  export function ship(): void {}
}
