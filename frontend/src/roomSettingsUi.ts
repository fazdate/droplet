import type { HaSensors, RoomClimateEntitiesUpdate, RoomSummary, SensorInfo } from './api';
import { createModalCloseButton } from './addPlantUi';
import { t } from './i18n';

export type SensorsStep =
  | { name: 'loading' }
  | { name: 'loaded'; sensors: HaSensors }
  | { name: 'error'; message: string };

export interface RoomSettingsModalOptions {
  room: RoomSummary | null;
  sensorsStep: SensorsStep;
  onSubmit: (payload: RoomClimateEntitiesUpdate) => void;
  onCancel: () => void;
}

const NONE_VALUE = 'none';

// Mirrors app.services.schedule.climate_factor_from_vpd — display-only (the
// backend remains the source of truth for the actual cadence), used so the
// modal can show "24h avg → cadence ×N" without a round trip.
const VPD_REFERENCE_KPA = 1.24;
const CLIMATE_FACTOR_MIN = 0.8;
const CLIMATE_FACTOR_MAX = 1.25;

function climateFactorFromVpd(vpdKpa: number): number {
  const raw = Math.pow(VPD_REFERENCE_KPA / vpdKpa, 0.5);
  return Math.min(CLIMATE_FACTOR_MAX, Math.max(CLIMATE_FACTOR_MIN, raw));
}

function buildSensorSelect(sensors: SensorInfo[], selected: string | null, className: string): HTMLSelectElement {
  const select = document.createElement('select');
  select.className = className;

  const noneOption = document.createElement('option');
  noneOption.value = NONE_VALUE;
  noneOption.textContent = t('roomSettings.notAssigned');
  select.appendChild(noneOption);

  for (const sensor of sensors) {
    const option = document.createElement('option');
    option.value = sensor.entity_id;
    option.textContent = sensor.friendly_name;
    select.appendChild(option);
  }

  select.value = selected ?? NONE_VALUE;
  return select;
}

function renderReadingSummary(room: RoomSummary): HTMLElement {
  const p = document.createElement('p');
  p.className = 'room-settings-reading-summary';

  const hasSensors = room.temperature_entity_id !== null || room.humidity_entity_id !== null;
  if (!hasSensors) {
    p.hidden = true;
    return p;
  }

  if (room.climate_temp_c === null || room.climate_humidity === null || room.climate_vpd_kpa === null) {
    p.textContent = t('roomSettings.noReadingYet');
    return p;
  }

  p.textContent = t('roomSettings.readingSummary', {
    temp: room.climate_temp_c.toFixed(1),
    humidity: Math.round(room.climate_humidity),
    vpd: room.climate_vpd_kpa.toFixed(2),
    factor: climateFactorFromVpd(room.climate_vpd_kpa).toFixed(2),
  });
  return p;
}

/**
 * "Room settings" modal (CLIMATE_CADENCE_PLAN.md) — assigns a room's Home
 * Assistant temperature/humidity sensors for the climate-aware watering
 * cadence, opened from the room "⋮" panel's "Room settings" button
 * (render.ts). Follows moveRoomUi.ts as its lightweight-modal template.
 */
export function renderRoomSettingsModal(container: HTMLElement, options: RoomSettingsModalOptions): void {
  container.replaceChildren();
  const { room, sensorsStep } = options;
  if (!room) {
    container.classList.add('hidden');
    return;
  }
  container.classList.remove('hidden');

  const modal = document.createElement('div');
  modal.className = 'add-plant-modal room-settings-modal';
  modal.appendChild(createModalCloseButton(() => options.onCancel()));

  const title = document.createElement('p');
  title.textContent = t('roomSettings.title', { name: room.name });
  modal.appendChild(title);

  if (sensorsStep.name === 'loading') {
    const loading = document.createElement('p');
    loading.textContent = t('roomSettings.loadingSensors');
    modal.appendChild(loading);
  } else if (sensorsStep.name === 'error') {
    const error = document.createElement('p');
    error.className = 'error-message';
    error.textContent = sensorsStep.message;
    modal.appendChild(error);
  } else {
    const form = document.createElement('form');
    form.className = 'room-settings-form';

    const temperatureLabel = document.createElement('label');
    temperatureLabel.textContent = t('roomSettings.temperatureLabel');
    const temperatureSelect = buildSensorSelect(
      sensorsStep.sensors.temperature,
      room.temperature_entity_id,
      'room-settings-temperature-select',
    );
    temperatureLabel.appendChild(temperatureSelect);
    form.appendChild(temperatureLabel);

    const humidityLabel = document.createElement('label');
    humidityLabel.textContent = t('roomSettings.humidityLabel');
    const humiditySelect = buildSensorSelect(
      sensorsStep.sensors.humidity,
      room.humidity_entity_id,
      'room-settings-humidity-select',
    );
    humidityLabel.appendChild(humiditySelect);
    form.appendChild(humidityLabel);

    form.appendChild(renderReadingSummary(room));

    const submit = document.createElement('button');
    submit.type = 'submit';
    submit.className = 'room-settings-submit';
    submit.textContent = t('action.save');
    form.appendChild(submit);

    form.addEventListener('submit', (event) => {
      event.preventDefault();
      options.onSubmit({
        temperature_entity_id: temperatureSelect.value === NONE_VALUE ? null : temperatureSelect.value,
        humidity_entity_id: humiditySelect.value === NONE_VALUE ? null : humiditySelect.value,
      });
    });

    modal.appendChild(form);
  }

  container.appendChild(modal);
}
