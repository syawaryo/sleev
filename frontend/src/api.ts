import axios from "axios";
import type { FloorData, CheckResponse } from "./types";

const BASE = "/api";

export async function getFloors(): Promise<{id: string; name: string; path: string; source?: string}[]> {
  const res = await axios.get(`${BASE}/floors`);
  return res.data;
}

export async function uploadDxf(file: File, label: string): Promise<{id: string; name: string; label: string; path: string}> {
  const form = new FormData();
  form.append("file", file);
  form.append("label", label);
  const res = await axios.post(`${BASE}/upload`, form);
  return res.data;
}

export async function uploadDwg(
  file: File,
  label: string,
): Promise<{id: string; name: string; label: string; path: string; source: string}> {
  const form = new FormData();
  form.append("file", file);
  form.append("label", label);
  const res = await axios.post(`${BASE}/upload_dwg`, form, {
    timeout: 300_000,  // 5 min — DWG conversion can be slow
  });
  return res.data;
}

export async function uploadIfc(
  files: File[],
  label: string,
): Promise<{id: string; name: string; label: string; path: string; source: string; file_count: number}> {
  if (files.length === 0) throw new Error("At least one IFC file is required");
  const form = new FormData();
  for (const f of files) form.append("files", f);
  form.append("label", label);
  const res = await axios.post(`${BASE}/upload_ifc`, form);
  return res.data;
}

export async function parseFloor(floorId: string): Promise<FloorData> {
  const res = await axios.post(`${BASE}/parse`, { floor_id: floorId });
  return res.data;
}

export async function runChecks(floor2fId: string, floor1fId?: string): Promise<CheckResponse> {
  const res = await axios.post(`${BASE}/check`, {
    floor_2f_id: floor2fId,
    floor_1f_id: floor1fId || null,
    wall_thickness: null,
    step_threshold: null,
  });
  return res.data;
}
