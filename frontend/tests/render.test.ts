import { describe, expect, it, vi } from 'vitest';
import type { PlantOut, RoomSummary } from '../src/api';
import { renderApp, sortRoomsByUrgency, sortPlantsByUrgency } from '../src/render';

const now = new Date('2026-08-17T09:00:00Z');

function room(overrides: Partial<RoomSummary>): RoomSummary {
  return { id: 1, name: 'Kitchen', sort_order: 0, plant_count: 0, due_count: 0, overdue_count: 0, ...overrides };
}

function plant(overrides: Partial<PlantOut>): PlantOut {
  return {
    id: 1,
    nickname: 'Basil',
    nickname_is_custom: false,
    room_id: 1,
    room_name: 'Kitchen',
    species_id: 1,
    species_common_name: null,
    photo_path: 'basil.jpg',
    next_due_at: null,
    last_watered_at: null,
    is_overdue: false,
    watering_interval_days_override: null,
    seasonal_adjust_enabled: true,
    recommended_interval_days: 7,
    care_source: 'perenual',
    light: null,
    soil: null,
    notes: null,
    ...overrides,
  };
}

describe('sortRoomsByUrgency', () => {
  it('should_put_rooms_with_more_overdue_plants_first', () => {
    const rooms = [room({ id: 1, name: 'A', overdue_count: 0 }), room({ id: 2, name: 'B', overdue_count: 2 })];

    const sorted = sortRoomsByUrgency(rooms);

    expect(sorted.map((r) => r.id)).toEqual([2, 1]);
  });

  it('should_fall_back_to_sort_order_when_overdue_counts_equal', () => {
    const rooms = [room({ id: 1, sort_order: 2, overdue_count: 0 }), room({ id: 2, sort_order: 1, overdue_count: 0 })];

    const sorted = sortRoomsByUrgency(rooms);

    expect(sorted.map((r) => r.id)).toEqual([2, 1]);
  });
});

describe('sortPlantsByUrgency', () => {
  it('should_order_overdue_before_due_soon_before_later', () => {
    const later = plant({ id: 1, next_due_at: '2026-08-25T09:00:00Z', is_overdue: false });
    const overdue = plant({ id: 2, next_due_at: '2026-08-10T09:00:00Z', is_overdue: true });
    const dueToday = plant({ id: 3, next_due_at: '2026-08-17T09:00:00Z', is_overdue: false });

    const sorted = sortPlantsByUrgency([later, overdue, dueToday]);

    expect(sorted.map((p) => p.id)).toEqual([2, 3, 1]);
  });
});

function baseOptions(overrides: Partial<import('../src/render').RenderAppOptions> = {}) {
  return {
    rooms: [] as RoomSummary[],
    plants: [] as PlantOut[],
    now,
    onWaterPlant: vi.fn(),
    onWaterRoom: vi.fn(),
    expandedPlantId: null,
    onToggleDetail: vi.fn(),
    onSetIntervalDays: vi.fn(),
    onResetInterval: vi.fn(),
    onRemovePlant: vi.fn(),
    onRemoveRoom: vi.fn(),
    onChangePhoto: vi.fn(),
    onRenameNickname: vi.fn(),
    onOpenMoveRoom: vi.fn(),
    expandedRoomId: null,
    onToggleRoomDetail: vi.fn(),
    onRenameRoom: vi.fn(),
    ...overrides,
  };
}

describe('renderApp', () => {
  it('should_render_room_header_with_overdue_count', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1, name: 'Kitchen', plant_count: 2, overdue_count: 1 })],
        plants: [plant({ id: 1, room_id: 1 }), plant({ id: 2, room_id: 1 })],
      }),
    );

    const header = container.querySelector('.room-header');
    expect(header?.textContent).toContain('Kitchen');
    expect(header?.textContent).toContain('1 need water');
  });

  it('should_render_a_top_summary_of_plants_needing_attention', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [
          room({ id: 1, overdue_count: 2, due_count: 1 }),
          room({ id: 2, overdue_count: 0, due_count: 3 }),
        ],
      }),
    );

    const summary = container.querySelector('.page-summary');
    expect(summary?.textContent).toContain('6 plants need attention');
  });

  it('should_request_a_thumbnail_rather_than_the_full_photo_for_a_plant_tile', () => {
    // Memory-friendliness (see TODO.md): the tile only ever displays this at
    // 64x64 CSS px, so it should ask for the small server-generated
    // thumbnail instead of the full up-to-1280px upload.
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1, plant_count: 1 })],
        plants: [plant({ id: 1, room_id: 1, photo_path: 'basil.jpg' })],
      }),
    );

    const img = container.querySelector<HTMLImageElement>('.plant-tile img')!;
    expect(img.src).toContain('/photos/thumbnails/basil.jpg');
    expect(img.loading).toBe('lazy');
    expect(img.decoding).toBe('async');
  });

  it('should_fall_back_to_the_full_photo_when_the_thumbnail_fails_to_load', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1, plant_count: 1 })],
        plants: [plant({ id: 1, room_id: 1, photo_path: 'basil.jpg' })],
      }),
    );

    const img = container.querySelector<HTMLImageElement>('.plant-tile img')!;
    img.dispatchEvent(new Event('error'));

    expect(img.src).toContain('/photos/basil.jpg');
    expect(img.src).not.toContain('/thumbnails/');
  });

  it('should_call_onWaterPlant_when_water_button_clicked', () => {
    const container = document.createElement('div');
    const onWaterPlant = vi.fn();

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1 })],
        plants: [plant({ id: 42, room_id: 1, nickname: 'Fern' })],
        onWaterPlant,
      }),
    );

    const button = container.querySelector<HTMLButtonElement>('[data-water-plant="42"]');
    button?.click();

    expect(onWaterPlant).toHaveBeenCalledWith(42);
  });

  it('should_call_onWaterRoom_when_water_all_button_clicked', () => {
    const container = document.createElement('div');
    const onWaterRoom = vi.fn();

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 7, name: 'Bedroom', plant_count: 1 })],
        plants: [plant({ id: 1, room_id: 7 })],
        onWaterRoom,
      }),
    );

    const button = container.querySelector<HTMLButtonElement>('[data-water-room="7"]');
    button?.click();

    expect(onWaterRoom).toHaveBeenCalledWith(7);
  });

  it('should_not_render_water_all_button_when_room_is_empty', () => {
    const container = document.createElement('div');

    renderApp(container, baseOptions({ rooms: [room({ id: 7, name: 'Bedroom', plant_count: 0 })] }));

    expect(container.querySelector('[data-water-room="7"]')).toBeNull();
  });

  it('should_render_empty_state_when_no_plants', () => {
    const container = document.createElement('div');

    renderApp(container, baseOptions());

    expect(container.textContent).toContain('No plants yet');
  });

  it('should_call_onToggleDetail_when_detail_button_clicked', () => {
    const container = document.createElement('div');
    const onToggleDetail = vi.fn();

    renderApp(
      container,
      baseOptions({ rooms: [room({ id: 1 })], plants: [plant({ id: 5, room_id: 1 })], onToggleDetail }),
    );

    container.querySelector<HTMLButtonElement>('[data-detail-plant="5"]')?.click();

    expect(onToggleDetail).toHaveBeenCalledWith(5);
  });

  it('should_call_onChangePhoto_with_the_selected_file_from_the_expanded_detail_menu', () => {
    // The "Change photo" control lives behind the "⋮" detail menu (TODO.md:
    // "Option to add new picture for the plant" — deliberately not a
    // frequently-surfaced action).
    const container = document.createElement('div');
    const onChangePhoto = vi.fn();

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1 })],
        plants: [plant({ id: 5, room_id: 1 })],
        expandedPlantId: 5,
        onChangePhoto,
      }),
    );

    const input = container.querySelector<HTMLInputElement>('.change-photo-control input[type="file"]')!;
    const file = new File(['fake'], 'new.jpg', { type: 'image/jpeg' });
    Object.defineProperty(input, 'files', { value: [file] });
    input.dispatchEvent(new Event('change'));

    expect(onChangePhoto).toHaveBeenCalledWith(5, file);
  });

  it('should_not_render_change_photo_control_when_detail_is_collapsed', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({ rooms: [room({ id: 1 })], plants: [plant({ id: 5, room_id: 1 })], expandedPlantId: null }),
    );

    expect(container.querySelector('.change-photo-control')).toBeNull();
  });

  it('should_render_care_instructions_inside_the_expanded_plant_detail', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1 })],
        plants: [plant({ id: 5, room_id: 1, light: 'Bright indirect light' })],
        expandedPlantId: 5,
      }),
    );

    expect(container.querySelector('.care-info')?.textContent).toContain('Bright indirect light');
  });

  it('should_not_render_care_instructions_when_detail_is_collapsed', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1 })],
        plants: [plant({ id: 5, room_id: 1, light: 'Bright indirect light' })],
        expandedPlantId: null,
      }),
    );

    expect(container.querySelector('.care-info')).toBeNull();
  });

  it('should_show_add_nickname_label_when_plant_has_no_custom_nickname', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1 })],
        plants: [plant({ id: 5, room_id: 1, nickname_is_custom: false })],
        expandedPlantId: 5,
      }),
    );

    const button = container.querySelector<HTMLButtonElement>('[data-rename-nickname="5"]')!;
    expect(button.textContent).toBe('Add nickname');
  });

  it('should_show_update_nickname_label_when_plant_already_has_a_custom_nickname', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1 })],
        plants: [plant({ id: 5, room_id: 1, nickname_is_custom: true })],
        expandedPlantId: 5,
      }),
    );

    const button = container.querySelector<HTMLButtonElement>('[data-rename-nickname="5"]')!;
    expect(button.textContent).toBe('Update nickname');
  });

  it('should_call_onRenameNickname_when_rename_button_clicked', () => {
    const container = document.createElement('div');
    const onRenameNickname = vi.fn();

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1 })],
        plants: [plant({ id: 5, room_id: 1 })],
        expandedPlantId: 5,
        onRenameNickname,
      }),
    );

    container.querySelector<HTMLButtonElement>('[data-rename-nickname="5"]')?.click();

    expect(onRenameNickname).toHaveBeenCalledWith(5);
  });

  it('should_not_render_rename_nickname_control_when_detail_is_collapsed', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({ rooms: [room({ id: 1 })], plants: [plant({ id: 5, room_id: 1 })], expandedPlantId: null }),
    );

    expect(container.querySelector('.rename-nickname-control')).toBeNull();
  });

  it('should_render_move_room_button_only_when_expanded_and_other_rooms_exist', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1, name: 'Kitchen' }), room({ id: 2, name: 'Bedroom' })],
        plants: [plant({ id: 5, room_id: 1 })],
        expandedPlantId: 5,
      }),
    );

    expect(container.querySelector('[data-move-to-room="5"]')).not.toBeNull();
  });

  it('should_not_render_move_room_control_when_there_is_no_other_room', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1, name: 'Kitchen' })],
        plants: [plant({ id: 5, room_id: 1 })],
        expandedPlantId: 5,
      }),
    );

    expect(container.querySelector('[data-move-to-room="5"]')).toBeNull();
  });

  it('should_not_leave_an_empty_move_room_wrapper_when_there_is_no_other_room', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1, name: 'Kitchen' })],
        plants: [plant({ id: 5, room_id: 1 })],
        expandedPlantId: 5,
      }),
    );

    expect(container.querySelector('.move-room-control')).toBeNull();
  });

  it('should_group_the_expanded_detail_actions_in_a_single_stack', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1, name: 'Kitchen' }), room({ id: 2, name: 'Bedroom' })],
        plants: [plant({ id: 5, room_id: 1 })],
        expandedPlantId: 5,
      }),
    );

    const actions = container.querySelector('.plant-detail-actions');
    expect(actions).not.toBeNull();
    expect(actions?.querySelectorAll('button').length).toBeGreaterThanOrEqual(2);
  });

  it('should_call_onOpenMoveRoom_with_the_plant_id_when_move_button_clicked', () => {
    const container = document.createElement('div');
    const onOpenMoveRoom = vi.fn();

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1, name: 'Kitchen' }), room({ id: 2, name: 'Bedroom' })],
        plants: [plant({ id: 5, room_id: 1 })],
        expandedPlantId: 5,
        onOpenMoveRoom,
      }),
    );

    container.querySelector<HTMLButtonElement>('[data-move-to-room="5"]')?.click();

    expect(onOpenMoveRoom).toHaveBeenCalledWith(5);
  });

  it('should_not_render_move_room_control_when_detail_is_collapsed', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1 }), room({ id: 2 })],
        plants: [plant({ id: 5, room_id: 1 })],
        expandedPlantId: null,
      }),
    );

    expect(container.querySelector('.move-room-control')).toBeNull();
  });

  it('should_render_cadence_editor_for_expanded_plant_only', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1 })],
        plants: [plant({ id: 5, room_id: 1 }), plant({ id: 6, room_id: 1 })],
        expandedPlantId: 5,
      }),
    );

    expect(container.querySelectorAll('.plant-detail').length).toBe(1);
    expect(container.querySelectorAll('.cadence-editor').length).toBe(1);
  });

  it('should_call_onSetIntervalDays_from_expanded_cadence_editor', () => {
    const container = document.createElement('div');
    const onSetIntervalDays = vi.fn();

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1 })],
        plants: [plant({ id: 5, room_id: 1, recommended_interval_days: 7 })],
        expandedPlantId: 5,
        onSetIntervalDays,
      }),
    );

    container.querySelector<HTMLButtonElement>('.stepper-plus')?.click();

    expect(onSetIntervalDays).toHaveBeenCalledWith(5, 8);
  });

  it('should_not_render_remove_button_for_collapsed_plants', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1 })],
        plants: [plant({ id: 5, room_id: 1 })],
      }),
    );

    expect(container.querySelector('[data-remove-plant]')).toBeNull();
  });

  it('should_call_onRemovePlant_when_remove_button_clicked', () => {
    const container = document.createElement('div');
    const onRemovePlant = vi.fn();

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1 })],
        plants: [plant({ id: 5, room_id: 1 })],
        expandedPlantId: 5,
        onRemovePlant,
      }),
    );

    container.querySelector<HTMLButtonElement>('[data-remove-plant="5"]')?.click();

    expect(onRemovePlant).toHaveBeenCalledWith(5);
  });

  it('should_not_render_remove_room_button_when_room_has_plants', () => {
    const container = document.createElement('div');

    renderApp(
      container,
      baseOptions({
        rooms: [room({ id: 1, plant_count: 1 })],
        plants: [plant({ id: 5, room_id: 1 })],
      }),
    );

    expect(container.querySelector('[data-remove-room]')).toBeNull();
  });

  it('should_render_remove_room_button_when_room_is_empty', () => {
    const container = document.createElement('div');

    renderApp(container, baseOptions({ rooms: [room({ id: 1, plant_count: 0 })] }));

    expect(container.querySelector('[data-remove-room="1"]')).not.toBeNull();
  });

  it('should_call_onRemoveRoom_when_remove_room_button_clicked', () => {
    const container = document.createElement('div');
    const onRemoveRoom = vi.fn();

    renderApp(container, baseOptions({ rooms: [room({ id: 7, plant_count: 0 })], onRemoveRoom }));

    container.querySelector<HTMLButtonElement>('[data-remove-room="7"]')?.click();

    expect(onRemoveRoom).toHaveBeenCalledWith(7);
  });

  it('should_not_render_room_detail_by_default', () => {
    const container = document.createElement('div');

    renderApp(container, baseOptions({ rooms: [room({ id: 1 })] }));

    expect(container.querySelector('.room-detail')).toBeNull();
  });

  it('should_call_onToggleRoomDetail_when_room_detail_toggle_clicked', () => {
    const container = document.createElement('div');
    const onToggleRoomDetail = vi.fn();

    renderApp(container, baseOptions({ rooms: [room({ id: 3 })], onToggleRoomDetail }));

    container.querySelector<HTMLButtonElement>('[data-detail-room="3"]')?.click();

    expect(onToggleRoomDetail).toHaveBeenCalledWith(3);
  });

  it('should_render_rename_room_button_when_room_detail_expanded', () => {
    const container = document.createElement('div');

    renderApp(container, baseOptions({ rooms: [room({ id: 4 })], expandedRoomId: 4 }));

    expect(container.querySelector('[data-rename-room="4"]')).not.toBeNull();
  });

  it('should_call_onRenameRoom_when_rename_room_button_clicked', () => {
    const container = document.createElement('div');
    const onRenameRoom = vi.fn();

    renderApp(container, baseOptions({ rooms: [room({ id: 4 })], expandedRoomId: 4, onRenameRoom }));

    container.querySelector<HTMLButtonElement>('[data-rename-room="4"]')?.click();

    expect(onRenameRoom).toHaveBeenCalledWith(4);
  });
});
