export interface Sleeve {
  id: string;
  center: [number, number];
  diameter: number;
  label_text: string | null;
  fl_text: string | null;
  pn_number: string | null;
  layer: string;
  discipline: string;
}

export interface GridLine {
  axis_label: string;
  direction: "H" | "V";
  position: number;
}

export interface WallLine {
  start: [number, number];
  end: [number, number];
  layer: string;
  wall_type: string;
}

export interface StepLine {
  start: [number, number];
  end: [number, number];
  layer: string;
}

export interface ColumnLine {
  start: [number, number];
  end: [number, number];
  layer: string;
}

export interface DimLine {
  layer: string;
  measurement: number;
  defpoint1: [number, number];
  defpoint2: [number, number];
  text_override: string | null;
}

export interface SlabZone {
  x: number;
  y: number;
  fl_text: string;
  fl_value: number;  // mm offset from FL, e.g. +40, -360
}

export interface FloorData {
  sleeves: Sleeve[];
  grid_lines: GridLine[];
  wall_lines: WallLine[];
  step_lines: StepLine[];
  column_lines: ColumnLine[];
  dim_lines: DimLine[];
  slab_zones: SlabZone[];
  slab_level: string | null;
}

export interface CheckResult {
  check_id: number;
  check_name: string;
  severity: "NG" | "WARNING" | "OK";
  sleeve_id: string | null;
  message: string;
  related_coords: [number, number][];
}

export interface CheckResponse {
  results: CheckResult[];
  summary: { ng: number; warning: number; ok: number };
}
