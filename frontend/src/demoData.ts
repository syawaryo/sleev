import type { CheckDef, CheckResult, FloorData, Sleeve } from "./types";
import type { AllEntitiesResponse } from "./api";

export interface DemoFloor {
  id: string;
  label: string;
  source: "dxf";
  lowerFloorId: string | null;
  drawingFile: string;
  entitiesFile: string;
  sleeves: Sleeve[];
  results: CheckResult[];
}

export interface DemoManifest {
  schemaVersion: number;
  generatedAt: string;
  checklistName: string;
  checklistNote: string;
  checks: CheckDef[];
  floors: DemoFloor[];
}

const drawings = new Map<string, Promise<FloorData>>();
const entities = new Map<string, Promise<AllEntitiesResponse>>();
async function readJson<T>(path: string): Promise<T> {
  const response = await fetch(`${import.meta.env.BASE_URL}demo/${path}`);
  if (!response.ok) throw new Error(`展示データを読み込めませんでした（${response.status}）`);
  return response.json() as Promise<T>;
}

export async function loadManifest(): Promise<DemoManifest> {
  const data = await readJson<DemoManifest>("manifest.json");
  if (data.schemaVersion !== 1 || !data.floors?.length) throw new Error("展示データがありません。データを生成してから開いてください。");
  return data;
}

export function loadDrawing(floor: DemoFloor): Promise<FloorData> {
  let promise = drawings.get(floor.drawingFile);
  if (!promise) {
    promise = readJson<FloorData>(floor.drawingFile).catch((error: unknown) => {
      drawings.delete(floor.drawingFile);
      throw error;
    });
    drawings.set(floor.drawingFile, promise);
  }
  return promise;
}

export function listFloorData(floor: DemoFloor): FloorData {
  return { sleeves: floor.sleeves, grid_lines: [], wall_lines: [], step_lines: [],
    column_lines: [], dim_lines: [], slab_zones: [], slab_outlines: [],
    recess_polygons: [], slab_labels: [], pn_labels: [], slab_level: null };
}

export function loadEntities(floor: DemoFloor): Promise<AllEntitiesResponse> {
  let promise = entities.get(floor.entitiesFile);
  if (!promise) {
    promise = readJson<AllEntitiesResponse>(floor.entitiesFile).catch((error: unknown) => {
      entities.delete(floor.entitiesFile);
      throw error;
    });
    entities.set(floor.entitiesFile, promise);
  }
  return promise;
}
