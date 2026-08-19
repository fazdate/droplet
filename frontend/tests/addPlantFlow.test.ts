import { describe, expect, it, vi } from 'vitest';
import { AddPlantFlow } from '../src/addPlantFlow';
import type { IdentifyCandidate } from '../src/api';

function candidate(overrides: Partial<IdentifyCandidate> = {}): IdentifyCandidate {
  return {
    species_id: 1,
    scientific_name: 'Monstera deliciosa',
    common_name: 'Swiss cheese plant',
    confidence: 0.9,
    reference_image_url: 'https://example.com/m.jpg',
    ...overrides,
  };
}

function makeDeps(overrides: Partial<import('../src/addPlantFlow').AddPlantDeps> = {}) {
  return {
    identifyPhoto: vi.fn(),
    lookupSpecies: vi.fn(),
    createManualSpecies: vi.fn(),
    createPlant: vi.fn(),
    createRoom: vi.fn(),
    ...overrides,
  };
}

describe('AddPlantFlow', () => {
  it('should_start_in_idle_step_and_render_it_immediately', () => {
    const render = vi.fn();
    new AddPlantFlow(makeDeps(), render, vi.fn());

    expect(render).toHaveBeenCalledWith({ name: 'idle' });
  });

  it('should_move_to_candidates_step_after_successful_identify', async () => {
    const deps = makeDeps({
      identifyPhoto: vi.fn().mockResolvedValue({ photo_id: 'p1.jpg', candidates: [candidate()] }),
    });
    const render = vi.fn();
    const flow = new AddPlantFlow(deps, render, vi.fn());

    await flow.submitPhoto(new File(['x'], 'p.jpg'));

    expect(render).toHaveBeenLastCalledWith({ name: 'candidates', photoId: 'p1.jpg', candidates: [candidate()] });
  });

  it('should_go_straight_to_manual_when_no_candidates_returned', async () => {
    const deps = makeDeps({ identifyPhoto: vi.fn().mockResolvedValue({ photo_id: 'p1.jpg', candidates: [] }) });
    const render = vi.fn();
    const flow = new AddPlantFlow(deps, render, vi.fn());

    await flow.submitPhoto(new File(['x'], 'p.jpg'));

    expect(render).toHaveBeenLastCalledWith({ name: 'manual', photoId: 'p1.jpg' });
  });

  it('should_show_error_when_identify_fails', async () => {
    const deps = makeDeps({ identifyPhoto: vi.fn().mockRejectedValue(new Error('network down')) });
    const render = vi.fn();
    const flow = new AddPlantFlow(deps, render, vi.fn());

    await flow.submitPhoto(new File(['x'], 'p.jpg'));

    expect(flow.getStep()).toEqual({
      name: 'error',
      message: 'Could not identify this photo. Try again or enter it manually.',
      photoId: '',
    });
  });

  it('should_move_to_manual_step_when_all_candidates_rejected', async () => {
    const deps = makeDeps({
      identifyPhoto: vi.fn().mockResolvedValue({ photo_id: 'p1.jpg', candidates: [candidate()] }),
    });
    const render = vi.fn();
    const flow = new AddPlantFlow(deps, render, vi.fn());
    await flow.submitPhoto(new File(['x'], 'p.jpg'));

    flow.rejectAllCandidates();

    expect(flow.getStep()).toEqual({ name: 'manual', photoId: 'p1.jpg' });
  });

  it('should_move_to_nickname_prompt_when_a_candidate_is_chosen', async () => {
    const deps = makeDeps({
      identifyPhoto: vi.fn().mockResolvedValue({ photo_id: 'p1.jpg', candidates: [candidate()] }),
    });
    const render = vi.fn();
    const flow = new AddPlantFlow(deps, render, vi.fn());
    await flow.submitPhoto(new File(['x'], 'p.jpg'));

    flow.chooseCandidate(candidate());

    expect(flow.getStep()).toEqual({
      name: 'nickname-prompt',
      photoId: 'p1.jpg',
      species_id: 1,
      defaultName: 'Swiss cheese plant',
    });
  });

  it('should_use_scientific_name_as_default_name_when_common_name_missing', async () => {
    const deps = makeDeps({
      identifyPhoto: vi.fn().mockResolvedValue({ photo_id: 'p1.jpg', candidates: [candidate({ common_name: null })] }),
    });
    const render = vi.fn();
    const flow = new AddPlantFlow(deps, render, vi.fn());
    await flow.submitPhoto(new File(['x'], 'p.jpg'));

    flow.chooseCandidate(candidate({ common_name: null }));

    expect(flow.getStep()).toMatchObject({ defaultName: 'Monstera deliciosa' });
  });

  it('should_search_by_name_and_return_candidates', async () => {
    const deps = makeDeps({ lookupSpecies: vi.fn().mockResolvedValue({ candidates: [candidate()] }) });
    const flow = new AddPlantFlow(deps, vi.fn(), vi.fn());

    const results = await flow.searchByName('monstera');

    expect(deps.lookupSpecies).toHaveBeenCalledWith('monstera');
    expect(results).toEqual([candidate()]);
  });

  it('should_create_manual_species_and_move_to_nickname_prompt', async () => {
    const deps = makeDeps({
      identifyPhoto: vi.fn().mockResolvedValue({ photo_id: 'p1.jpg', candidates: [] }),
      createManualSpecies: vi.fn().mockResolvedValue({ species_id: 55 }),
    });
    const render = vi.fn();
    const flow = new AddPlantFlow(deps, render, vi.fn());
    await flow.submitPhoto(new File(['x'], 'p.jpg'));

    await flow.submitManual('My weird cactus', 20);

    expect(deps.createManualSpecies).toHaveBeenCalledWith('My weird cactus', 20);
    expect(flow.getStep()).toEqual({
      name: 'nickname-prompt',
      photoId: 'p1.jpg',
      species_id: 55,
      defaultName: 'My weird cactus',
    });
  });

  it('should_never_dead_end_when_manual_species_creation_fails', async () => {
    const deps = makeDeps({
      identifyPhoto: vi.fn().mockResolvedValue({ photo_id: 'p1.jpg', candidates: [] }),
      createManualSpecies: vi.fn().mockRejectedValue(new Error('boom')),
    });
    const flow = new AddPlantFlow(deps, vi.fn(), vi.fn());
    await flow.submitPhoto(new File(['x'], 'p.jpg'));

    await flow.submitManual('X', 7);

    expect(flow.getStep().name).toBe('error');
  });

  it('should_move_to_room_picker_without_nickname_when_skipped', async () => {
    const deps = makeDeps({
      identifyPhoto: vi.fn().mockResolvedValue({ photo_id: 'p1.jpg', candidates: [candidate()] }),
    });
    const flow = new AddPlantFlow(deps, vi.fn(), vi.fn());
    await flow.submitPhoto(new File(['x'], 'p.jpg'));
    flow.chooseCandidate(candidate());

    flow.skipNickname();

    expect(flow.getStep()).toEqual({ name: 'room-picker', photoId: 'p1.jpg', species_id: 1 });
  });

  it('should_move_to_room_picker_with_custom_nickname_when_set', async () => {
    const deps = makeDeps({
      identifyPhoto: vi.fn().mockResolvedValue({ photo_id: 'p1.jpg', candidates: [candidate()] }),
    });
    const flow = new AddPlantFlow(deps, vi.fn(), vi.fn());
    await flow.submitPhoto(new File(['x'], 'p.jpg'));
    flow.chooseCandidate(candidate());

    flow.setNickname('Monty');

    expect(flow.getStep()).toEqual({
      name: 'room-picker',
      photoId: 'p1.jpg',
      species_id: 1,
      nickname: 'Monty',
    });
  });

  it('should_treat_a_blank_custom_nickname_as_no_nickname', async () => {
    const deps = makeDeps({
      identifyPhoto: vi.fn().mockResolvedValue({ photo_id: 'p1.jpg', candidates: [candidate()] }),
    });
    const flow = new AddPlantFlow(deps, vi.fn(), vi.fn());
    await flow.submitPhoto(new File(['x'], 'p.jpg'));
    flow.chooseCandidate(candidate());

    flow.setNickname('   ');

    expect(flow.getStep()).toEqual({ name: 'room-picker', photoId: 'p1.jpg', species_id: 1 });
  });

  it('should_create_plant_with_existing_room_and_call_onPlantCreated', async () => {
    const createdPlant = { id: 9, nickname: 'Monty' };
    const deps = makeDeps({
      identifyPhoto: vi.fn().mockResolvedValue({ photo_id: 'p1.jpg', candidates: [candidate()] }),
      createPlant: vi.fn().mockResolvedValue(createdPlant),
    });
    const onPlantCreated = vi.fn();
    const flow = new AddPlantFlow(deps, vi.fn(), onPlantCreated);
    await flow.submitPhoto(new File(['x'], 'p.jpg'));
    flow.chooseCandidate(candidate());
    flow.setNickname('Monty');

    await flow.submitRoomAndCreate({ roomId: 3 });

    expect(deps.createPlant).toHaveBeenCalledWith({
      photo_id: 'p1.jpg',
      species_id: 1,
      room_id: 3,
      nickname: 'Monty',
    });
    expect(onPlantCreated).toHaveBeenCalledWith(createdPlant);
    expect(flow.getStep()).toEqual({ name: 'idle' });
  });

  it('should_create_plant_without_nickname_when_skipped', async () => {
    const createdPlant = { id: 9, nickname: 'Swiss cheese plant #1' };
    const deps = makeDeps({
      identifyPhoto: vi.fn().mockResolvedValue({ photo_id: 'p1.jpg', candidates: [candidate()] }),
      createPlant: vi.fn().mockResolvedValue(createdPlant),
    });
    const flow = new AddPlantFlow(deps, vi.fn(), vi.fn());
    await flow.submitPhoto(new File(['x'], 'p.jpg'));
    flow.chooseCandidate(candidate());
    flow.skipNickname();

    await flow.submitRoomAndCreate({ roomId: 3 });

    expect(deps.createPlant).toHaveBeenCalledWith({
      photo_id: 'p1.jpg',
      species_id: 1,
      room_id: 3,
      nickname: undefined,
    });
  });

  it('should_create_a_new_room_first_when_new_room_name_given', async () => {
    const deps = makeDeps({
      identifyPhoto: vi.fn().mockResolvedValue({ photo_id: 'p1.jpg', candidates: [candidate()] }),
      createRoom: vi.fn().mockResolvedValue({ id: 42, name: 'Attic' }),
      createPlant: vi.fn().mockResolvedValue({ id: 1 }),
    });
    const flow = new AddPlantFlow(deps, vi.fn(), vi.fn());
    await flow.submitPhoto(new File(['x'], 'p.jpg'));
    flow.chooseCandidate(candidate());
    flow.skipNickname();

    await flow.submitRoomAndCreate({ newRoomName: 'Attic' });

    expect(deps.createRoom).toHaveBeenCalledWith('Attic');
    expect(deps.createPlant).toHaveBeenCalledWith(expect.objectContaining({ room_id: 42 }));
  });

  it('should_go_to_error_step_when_plant_creation_fails', async () => {
    const deps = makeDeps({
      identifyPhoto: vi.fn().mockResolvedValue({ photo_id: 'p1.jpg', candidates: [candidate()] }),
      createPlant: vi.fn().mockRejectedValue(new Error('boom')),
    });
    const flow = new AddPlantFlow(deps, vi.fn(), vi.fn());
    await flow.submitPhoto(new File(['x'], 'p.jpg'));
    flow.chooseCandidate(candidate());
    flow.skipNickname();

    await flow.submitRoomAndCreate({ roomId: 1 });

    expect(flow.getStep().name).toBe('error');
  });

  it('should_return_to_idle_on_cancel', async () => {
    const deps = makeDeps({
      identifyPhoto: vi.fn().mockResolvedValue({ photo_id: 'p1.jpg', candidates: [candidate()] }),
    });
    const flow = new AddPlantFlow(deps, vi.fn(), vi.fn());
    await flow.submitPhoto(new File(['x'], 'p.jpg'));

    flow.cancel();

    expect(flow.getStep()).toEqual({ name: 'idle' });
  });
});
