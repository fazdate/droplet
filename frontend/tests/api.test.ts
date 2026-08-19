import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  cancelAway,
  createManualSpecies,
  createPlant,
  createRoom,
  deletePlant,
  deleteRoom,
  diagnosePlant,
  fetchPlants,
  fetchRooms,
  identifyPhoto,
  lookupSpecies,
  renameRoom,
  resetPlantInterval,
  setAway,
  snoozePlant,
  undoWatering,
  updatePlantInterval,
  updatePlantNickname,
  updatePlantRoom,
  updatePlantPhoto,
  waterPlant,
  waterRoom,
} from '../src/api';

function mockFetchOnce(body: unknown, ok = true, status = 200): void {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok,
      status,
      statusText: 'error',
      json: async () => body,
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('api client', () => {
  it('should_fetch_rooms_from_expected_endpoint', async () => {
    mockFetchOnce([{ id: 1, name: 'Kitchen', sort_order: 0, plant_count: 2, due_count: 1, overdue_count: 0 }]);

    const rooms = await fetchRooms();

    expect(fetch).toHaveBeenCalledWith('/api/rooms');
    expect(rooms[0].name).toBe('Kitchen');
  });

  it('should_fetch_plants_from_expected_endpoint', async () => {
    mockFetchOnce([]);

    await fetchPlants();

    expect(fetch).toHaveBeenCalledWith('/api/plants');
  });

  it('should_post_to_water_single_plant_endpoint', async () => {
    mockFetchOnce({ undo_token: 'abc', plant_ids: [5] });

    const result = await waterPlant(5);

    expect(fetch).toHaveBeenCalledWith('/api/plants/5/water', { method: 'POST' });
    expect(result.undo_token).toBe('abc');
  });

  it('should_post_to_water_room_endpoint', async () => {
    mockFetchOnce({ undo_token: 'abc', plant_ids: [1, 2] });

    await waterRoom(9);

    expect(fetch).toHaveBeenCalledWith('/api/rooms/9/water', { method: 'POST' });
  });

  it('should_post_token_to_undo_endpoint', async () => {
    mockFetchOnce({ restored_plant_ids: [5] });

    const result = await undoWatering('abc');

    expect(fetch).toHaveBeenCalledWith('/api/undo', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: 'abc' }),
    });
    expect(result.restored_plant_ids).toEqual([5]);
  });

  it('should_throw_when_response_not_ok', async () => {
    mockFetchOnce({}, false, 404);

    await expect(fetchRooms()).rejects.toThrow('Request failed: 404');
  });

  it('should_create_room', async () => {
    mockFetchOnce({ id: 2, name: 'Bedroom', sort_order: 0, plant_count: 0, due_count: 0, overdue_count: 0 });

    const room = await createRoom('Bedroom');

    expect(fetch).toHaveBeenCalledWith('/api/rooms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Bedroom' }),
    });
    expect(room.name).toBe('Bedroom');
  });

  it('should_delete_room', async () => {
    mockFetchOnce(null, true, 204);

    await deleteRoom(2);

    expect(fetch).toHaveBeenCalledWith('/api/rooms/2', { method: 'DELETE' });
  });

  it('should_throw_when_delete_room_response_not_ok', async () => {
    mockFetchOnce({ detail: 'Room still has plants' }, false, 409);

    await expect(deleteRoom(2)).rejects.toThrow('Request failed: 409');
  });

  it('should_rename_room', async () => {
    mockFetchOnce({ id: 2, name: 'Bedroom', sort_order: 0 });

    const room = await renameRoom(2, 'Bedroom');

    expect(fetch).toHaveBeenCalledWith('/api/rooms/2', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'Bedroom' }),
    });
    expect(room.name).toBe('Bedroom');
  });

  it('should_throw_when_rename_room_response_not_ok', async () => {
    mockFetchOnce({ detail: 'Room name already exists' }, false, 409);

    await expect(renameRoom(2, 'Bedroom')).rejects.toThrow('Request failed: 409');
  });

  it('should_identify_photo_via_multipart_upload', async () => {
    mockFetchOnce({ photo_id: 'abc.jpg', candidates: [] });
    const file = new File(['fake'], 'plant.jpg', { type: 'image/jpeg' });

    const result = await identifyPhoto(file);

    expect(fetch).toHaveBeenCalledWith('/api/identify', {
      method: 'POST',
      body: expect.any(FormData),
    });
    expect(result.photo_id).toBe('abc.jpg');
  });

  it('should_update_plant_photo_via_multipart_upload', async () => {
    mockFetchOnce({ id: 5, photo_path: 'new.jpg' });
    const file = new File(['fake'], 'plant.jpg', { type: 'image/jpeg' });

    const result = await updatePlantPhoto(5, file);

    expect(fetch).toHaveBeenCalledWith('/api/plants/5/photo', {
      method: 'POST',
      body: expect.any(FormData),
    });
    expect(result.photo_path).toBe('new.jpg');
  });

  it('should_diagnose_plant_via_multipart_upload', async () => {
    mockFetchOnce({
      healthy: false,
      issues: [{ issue: 'Yellowing leaves', suggestion: 'Water less often.' }],
    });
    const file = new File(['fake'], 'plant.jpg', { type: 'image/jpeg' });

    const result = await diagnosePlant(5, file);

    expect(fetch).toHaveBeenCalledWith('/api/plants/5/diagnose', {
      method: 'POST',
      body: expect.any(FormData),
    });
    expect(result.healthy).toBe(false);
    expect(result.issues).toEqual([{ issue: 'Yellowing leaves', suggestion: 'Water less often.' }]);
  });

  it('should_throw_when_diagnose_response_not_ok', async () => {
    mockFetchOnce({ detail: 'unavailable' }, false, 503);
    const file = new File(['fake'], 'plant.jpg', { type: 'image/jpeg' });

    await expect(diagnosePlant(5, file)).rejects.toThrow('Request failed: 503');
  });

  it('should_look_up_species_by_query_string', async () => {
    mockFetchOnce({ candidates: [] });

    await lookupSpecies('monstera');

    expect(fetch).toHaveBeenCalledWith('/api/species/lookup?q=monstera');
  });

  it('should_create_manual_species', async () => {
    mockFetchOnce({ species_id: 7 });

    const result = await createManualSpecies('My cactus', 20);

    expect(fetch).toHaveBeenCalledWith('/api/species/manual', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: 'My cactus', interval_days: 20 }),
    });
    expect(result.species_id).toBe(7);
  });

  it('should_create_plant', async () => {
    mockFetchOnce({ id: 1, nickname: 'Basil' });

    await createPlant({ photo_id: 'p.jpg', species_id: 1, room_id: 2, nickname: 'Basil' });

    expect(fetch).toHaveBeenCalledWith('/api/plants', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ photo_id: 'p.jpg', species_id: 1, room_id: 2, nickname: 'Basil' }),
    });
  });

  it('should_snooze_plant_for_given_days', async () => {
    mockFetchOnce({});

    await snoozePlant(5, 2);

    expect(fetch).toHaveBeenCalledWith('/api/plants/5/snooze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ days: 2 }),
    });
  });

  it('should_set_away_for_given_days', async () => {
    mockFetchOnce({});

    await setAway(3);

    expect(fetch).toHaveBeenCalledWith('/api/away', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ days: 3 }),
    });
  });

  it('should_cancel_away_with_empty_payload', async () => {
    mockFetchOnce({});

    await cancelAway();

    expect(fetch).toHaveBeenCalledWith('/api/away', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
  });

  it('should_update_plant_interval_override', async () => {
    mockFetchOnce({ id: 1, watering_interval_days_override: 10 });

    await updatePlantInterval(1, 10);

    expect(fetch).toHaveBeenCalledWith('/api/plants/1', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ interval_override: 10 }),
    });
  });

  it('should_update_plant_nickname', async () => {
    mockFetchOnce({ id: 1, nickname: 'Monty', nickname_is_custom: true });

    await updatePlantNickname(1, 'Monty');

    expect(fetch).toHaveBeenCalledWith('/api/plants/1', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nickname: 'Monty' }),
    });
  });

  it('should_update_plant_room', async () => {
    mockFetchOnce({ id: 1, room_id: 2 });

    await updatePlantRoom(1, 2);

    expect(fetch).toHaveBeenCalledWith('/api/plants/1', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ room_id: 2 }),
    });
  });

  it('should_reset_plant_interval_override', async () => {
    mockFetchOnce({ id: 1, watering_interval_days_override: null });

    await resetPlantInterval(1);

    expect(fetch).toHaveBeenCalledWith('/api/plants/1/interval-override', { method: 'DELETE' });
  });

  it('should_delete_plant', async () => {
    mockFetchOnce(null, true, 204);

    await deletePlant(5);

    expect(fetch).toHaveBeenCalledWith('/api/plants/5', { method: 'DELETE' });
  });

  it('should_throw_when_delete_plant_response_not_ok', async () => {
    mockFetchOnce(null, false, 404);

    await expect(deletePlant(5)).rejects.toThrow('Request failed: 404');
  });
});
