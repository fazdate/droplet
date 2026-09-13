import { describe, expect, it, vi } from 'vitest';
import type { HaSensors, RoomSummary } from '../src/api';
import { renderRoomSettingsModal } from '../src/roomSettingsUi';

function room(overrides: Partial<RoomSummary>): RoomSummary {
  return {
    id: 1,
    name: 'Balcony',
    sort_order: 0,
    plant_count: 0,
    due_count: 0,
    overdue_count: 0,
    temperature_entity_id: null,
    humidity_entity_id: null,
    climate_temp_c: null,
    climate_humidity: null,
    climate_vpd_kpa: null,
    climate_updated_at: null,
    ...overrides,
  };
}

const sensors: HaSensors = {
  temperature: [
    { entity_id: 'sensor.balcony_temp', friendly_name: 'Balcony Temperature', device_class: 'temperature', unit: '°C', state: '21' },
    { entity_id: 'sensor.kitchen_temp', friendly_name: 'Kitchen Temperature', device_class: 'temperature', unit: '°C', state: '22' },
  ],
  humidity: [
    { entity_id: 'sensor.balcony_humidity', friendly_name: 'Balcony Humidity', device_class: 'humidity', unit: '%', state: '50' },
  ],
};

describe('renderRoomSettingsModal', () => {
  it('should_hide_container_when_no_room', () => {
    const container = document.createElement('div');
    container.classList.remove('hidden');

    renderRoomSettingsModal(container, {
      room: null,
      sensorsStep: { name: 'loading' },
      onSubmit: vi.fn(),
      onCancel: vi.fn(),
    });

    expect(container.classList.contains('hidden')).toBe(true);
  });

  it('should_show_loading_message_while_sensors_load', () => {
    const container = document.createElement('div');

    renderRoomSettingsModal(container, {
      room: room({}),
      sensorsStep: { name: 'loading' },
      onSubmit: vi.fn(),
      onCancel: vi.fn(),
    });

    expect(container.querySelector('select')).toBeNull();
    expect(container.textContent).toContain('Loading sensors');
  });

  it('should_show_error_message_when_sensors_failed_to_load', () => {
    const container = document.createElement('div');

    renderRoomSettingsModal(container, {
      room: room({}),
      sensorsStep: { name: 'error', message: 'boom' },
      onSubmit: vi.fn(),
      onCancel: vi.fn(),
    });

    expect(container.textContent).toContain('boom');
  });

  it('should_populate_dropdowns_from_the_sensor_list', () => {
    const container = document.createElement('div');

    renderRoomSettingsModal(container, {
      room: room({}),
      sensorsStep: { name: 'loaded', sensors },
      onSubmit: vi.fn(),
      onCancel: vi.fn(),
    });

    const temperatureOptions = Array.from(
      container.querySelectorAll<HTMLOptionElement>('.room-settings-temperature-select option'),
    ).map((o) => o.value);
    const humidityOptions = Array.from(
      container.querySelectorAll<HTMLOptionElement>('.room-settings-humidity-select option'),
    ).map((o) => o.value);

    expect(temperatureOptions).toEqual(['none', 'sensor.balcony_temp', 'sensor.kitchen_temp']);
    expect(humidityOptions).toEqual(['none', 'sensor.balcony_humidity']);
  });

  it('should_preselect_the_rooms_current_assignment', () => {
    const container = document.createElement('div');

    renderRoomSettingsModal(container, {
      room: room({ temperature_entity_id: 'sensor.kitchen_temp', humidity_entity_id: 'sensor.balcony_humidity' }),
      sensorsStep: { name: 'loaded', sensors },
      onSubmit: vi.fn(),
      onCancel: vi.fn(),
    });

    const temperatureSelect = container.querySelector<HTMLSelectElement>('.room-settings-temperature-select')!;
    const humiditySelect = container.querySelector<HTMLSelectElement>('.room-settings-humidity-select')!;

    expect(temperatureSelect.value).toBe('sensor.kitchen_temp');
    expect(humiditySelect.value).toBe('sensor.balcony_humidity');
  });

  it('should_default_to_none_sentinel_when_unassigned', () => {
    const container = document.createElement('div');

    renderRoomSettingsModal(container, {
      room: room({}),
      sensorsStep: { name: 'loaded', sensors },
      onSubmit: vi.fn(),
      onCancel: vi.fn(),
    });

    const temperatureSelect = container.querySelector<HTMLSelectElement>('.room-settings-temperature-select')!;
    expect(temperatureSelect.value).toBe('none');
  });

  it('should_submit_null_when_none_sentinel_selected', () => {
    const container = document.createElement('div');
    const onSubmit = vi.fn();

    renderRoomSettingsModal(container, {
      room: room({ temperature_entity_id: 'sensor.kitchen_temp' }),
      sensorsStep: { name: 'loaded', sensors },
      onSubmit,
      onCancel: vi.fn(),
    });

    const temperatureSelect = container.querySelector<HTMLSelectElement>('.room-settings-temperature-select')!;
    temperatureSelect.value = 'none';
    container.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));

    expect(onSubmit).toHaveBeenCalledWith({ temperature_entity_id: null, humidity_entity_id: null });
  });

  it('should_submit_selected_entity_ids_as_the_save_payload', () => {
    const container = document.createElement('div');
    const onSubmit = vi.fn();

    renderRoomSettingsModal(container, {
      room: room({}),
      sensorsStep: { name: 'loaded', sensors },
      onSubmit,
      onCancel: vi.fn(),
    });

    const temperatureSelect = container.querySelector<HTMLSelectElement>('.room-settings-temperature-select')!;
    const humiditySelect = container.querySelector<HTMLSelectElement>('.room-settings-humidity-select')!;
    temperatureSelect.value = 'sensor.balcony_temp';
    humiditySelect.value = 'sensor.balcony_humidity';
    container.querySelector('form')!.dispatchEvent(new Event('submit', { cancelable: true }));

    expect(onSubmit).toHaveBeenCalledWith({
      temperature_entity_id: 'sensor.balcony_temp',
      humidity_entity_id: 'sensor.balcony_humidity',
    });
  });

  it('should_call_onCancel_when_close_button_clicked', () => {
    const container = document.createElement('div');
    const onCancel = vi.fn();

    renderRoomSettingsModal(container, {
      room: room({}),
      sensorsStep: { name: 'loaded', sensors },
      onSubmit: vi.fn(),
      onCancel,
    });

    container.querySelector<HTMLButtonElement>('.modal-close')?.click();

    expect(onCancel).toHaveBeenCalled();
  });

  it('should_show_reading_summary_with_latest_and_smoothed_values', () => {
    const container = document.createElement('div');

    renderRoomSettingsModal(container, {
      room: room({
        temperature_entity_id: 'sensor.balcony_temp',
        humidity_entity_id: 'sensor.balcony_humidity',
        climate_temp_c: 24,
        climate_humidity: 40,
        climate_vpd_kpa: 1.0,
      }),
      sensorsStep: { name: 'loaded', sensors },
      onSubmit: vi.fn(),
      onCancel: vi.fn(),
    });

    const summary = container.querySelector('.room-settings-reading-summary');
    expect(summary?.textContent).toContain('24.0');
    expect(summary?.textContent).toContain('40');
    expect(summary?.textContent).toContain('1.00');
  });

  it('should_not_show_reading_summary_when_no_sensors_assigned', () => {
    const container = document.createElement('div');

    renderRoomSettingsModal(container, {
      room: room({}),
      sensorsStep: { name: 'loaded', sensors },
      onSubmit: vi.fn(),
      onCancel: vi.fn(),
    });

    const summary = container.querySelector<HTMLElement>('.room-settings-reading-summary');
    expect(summary?.hidden).toBe(true);
  });
});
