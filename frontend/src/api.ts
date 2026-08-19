import { resizeImageForUpload } from './imageResize';

/** Types mirroring backend/app/schemas.py. */

export interface RoomSummary {
  id: number;
  name: string;
  sort_order: number;
  plant_count: number;
  due_count: number;
  overdue_count: number;
}

export interface PlantOut {
  id: number;
  nickname: string;
  nickname_is_custom: boolean;
  room_id: number;
  room_name: string;
  species_id: number;
  species_common_name: string | null;
  photo_path: string;
  next_due_at: string | null;
  last_watered_at: string | null;
  is_overdue: boolean;
  watering_interval_days_override: number | null;
  seasonal_adjust_enabled: boolean;
  recommended_interval_days: number;
  care_source: 'perenual' | 'llm' | 'default' | 'manual';
  light: string | null;
  soil: string | null;
  notes: string | null;
}

export interface WaterResult {
  undo_token: string;
  plant_ids: number[];
}

export interface UndoResult {
  restored_plant_ids: number[];
}

export interface IdentifyCandidate {
  species_id: number;
  scientific_name: string;
  common_name: string | null;
  confidence: number | null;
  reference_image_url: string | null;
}

export interface IdentifyResponse {
  photo_id: string;
  candidates: IdentifyCandidate[];
}

export interface SpeciesLookupResponse {
  candidates: IdentifyCandidate[];
}

export interface DiagnoseIssue {
  issue: string;
  suggestion: string;
}

export interface DiagnoseResponse {
  healthy: boolean;
  issues: DiagnoseIssue[];
}

export interface CreatePlantRequest {
  photo_id: string;
  species_id: number;
  room_id: number;
  nickname?: string;
  interval_override?: number;
}

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export function fetchRooms(): Promise<RoomSummary[]> {
  return fetch('/api/rooms').then((r) => json<RoomSummary[]>(r));
}

export function createRoom(name: string): Promise<RoomSummary> {
  return fetch('/api/rooms', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  }).then((r) => json<RoomSummary>(r));
}

export function renameRoom(roomId: number, name: string): Promise<{ id: number; name: string; sort_order: number }> {
  return fetch(`/api/rooms/${roomId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  }).then((r) => json<{ id: number; name: string; sort_order: number }>(r));
}

export function deleteRoom(roomId: number): Promise<void> {
  return fetch(`/api/rooms/${roomId}`, { method: 'DELETE' }).then((r) => {
    if (!r.ok) throw new Error(`Request failed: ${r.status}`);
  });
}

export function fetchPlants(): Promise<PlantOut[]> {
  return fetch('/api/plants').then((r) => json<PlantOut[]>(r));
}

export function waterPlant(plantId: number): Promise<WaterResult> {
  return fetch(`/api/plants/${plantId}/water`, { method: 'POST' }).then((r) => json<WaterResult>(r));
}

export function waterRoom(roomId: number): Promise<WaterResult> {
  return fetch(`/api/rooms/${roomId}/water`, { method: 'POST' }).then((r) => json<WaterResult>(r));
}

export function undoWatering(token: string): Promise<UndoResult> {
  return fetch('/api/undo', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  }).then((r) => json<UndoResult>(r));
}

export async function identifyPhoto(file: File): Promise<IdentifyResponse> {
  // Resize/compress client-side first (plan TODO) to cut upload size and
  // likely AI inference time; falls back to the original file if that fails.
  const uploadFile = await resizeImageForUpload(file);
  const body = new FormData();
  body.append('photo', uploadFile);
  return fetch('/api/identify', { method: 'POST', body }).then((r) => json<IdentifyResponse>(r));
}

export function lookupSpecies(query: string): Promise<SpeciesLookupResponse> {
  return fetch(`/api/species/lookup?q=${encodeURIComponent(query)}`).then((r) => json<SpeciesLookupResponse>(r));
}

export function createManualSpecies(name: string, intervalDays: number): Promise<{ species_id: number }> {
  return fetch('/api/species/manual', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, interval_days: intervalDays }),
  }).then((r) => json<{ species_id: number }>(r));
}

export function createPlant(payload: CreatePlantRequest): Promise<PlantOut> {
  return fetch('/api/plants', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }).then((r) => json<PlantOut>(r));
}

export function snoozePlant(plantId: number, days: number): Promise<void> {
  return fetch(`/api/plants/${plantId}/snooze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ days }),
  }).then((r) => {
    if (!r.ok) throw new Error(`Request failed: ${r.status}`);
  });
}

export function setAway(days: number): Promise<void> {
  return fetch('/api/away', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ days }),
  }).then((r) => {
    if (!r.ok) throw new Error(`Request failed: ${r.status}`);
  });
}

export function cancelAway(): Promise<void> {
  return fetch('/api/away', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  }).then((r) => {
    if (!r.ok) throw new Error(`Request failed: ${r.status}`);
  });
}

export function updatePlantInterval(plantId: number, intervalDays: number): Promise<PlantOut> {
  return fetch(`/api/plants/${plantId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ interval_override: intervalDays }),
  }).then((r) => json<PlantOut>(r));
}

export function updatePlantNickname(plantId: number, nickname: string): Promise<PlantOut> {
  return fetch(`/api/plants/${plantId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nickname }),
  }).then((r) => json<PlantOut>(r));
}

export function updatePlantRoom(plantId: number, roomId: number): Promise<PlantOut> {
  return fetch(`/api/plants/${plantId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ room_id: roomId }),
  }).then((r) => json<PlantOut>(r));
}

export function resetPlantInterval(plantId: number): Promise<PlantOut> {
  return fetch(`/api/plants/${plantId}/interval-override`, { method: 'DELETE' }).then((r) => json<PlantOut>(r));
}

export async function updatePlantPhoto(plantId: number, file: File): Promise<PlantOut> {
  const uploadFile = await resizeImageForUpload(file);
  const body = new FormData();
  body.append('photo', uploadFile);
  return fetch(`/api/plants/${plantId}/photo`, { method: 'POST', body }).then((r) => json<PlantOut>(r));
}

export function deletePlant(plantId: number): Promise<void> {
  return fetch(`/api/plants/${plantId}`, { method: 'DELETE' }).then((r) => {
    if (!r.ok) throw new Error(`Request failed: ${r.status}`);
  });
}

export async function diagnosePlant(plantId: number, file: File): Promise<DiagnoseResponse> {
  const uploadFile = await resizeImageForUpload(file);
  const body = new FormData();
  body.append('photo', uploadFile);
  return fetch(`/api/plants/${plantId}/diagnose`, { method: 'POST', body }).then((r) => json<DiagnoseResponse>(r));
}
