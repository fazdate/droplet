import { describe, expect, it } from 'vitest';
import { renderCareInfo } from '../src/careInfo';
import type { PlantOut } from '../src/api';

function plant(overrides: Partial<PlantOut> = {}): PlantOut {
  return {
    id: 1,
    nickname: 'Basil',
    nickname_is_custom: false,
    room_id: 1,
    room_name: 'Kitchen',
    species_id: 1,
    species_common_name: 'Sweet basil',
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

describe('renderCareInfo', () => {
  it('should_show_light_soil_and_notes_when_all_present', () => {
    const container = document.createElement('div');

    renderCareInfo(
      container,
      plant({ light: 'Bright indirect light', soil: 'Well-draining potting mix', notes: 'Likes humidity.' }),
    );

    expect(container.querySelector('.care-light')?.textContent).toContain('Bright indirect light');
    expect(container.querySelector('.care-soil')?.textContent).toContain('Well-draining potting mix');
    expect(container.querySelector('.care-notes')?.textContent).toContain('Likes humidity.');
  });

  it('should_omit_rows_for_fields_that_are_null', () => {
    const container = document.createElement('div');

    renderCareInfo(container, plant({ light: 'Bright indirect light', soil: null, notes: null }));

    expect(container.querySelector('.care-light')).not.toBeNull();
    expect(container.querySelector('.care-soil')).toBeNull();
    expect(container.querySelector('.care-notes')).toBeNull();
  });

  it('should_show_fallback_message_when_all_fields_are_null', () => {
    const container = document.createElement('div');

    renderCareInfo(container, plant({ light: null, soil: null, notes: null }));

    expect(container.querySelector('.care-info-empty')?.textContent).toBe(
      'No care details available yet for this plant.',
    );
    expect(container.querySelector('.care-light')).toBeNull();
  });

  it('should_show_heading', () => {
    const container = document.createElement('div');

    renderCareInfo(container, plant({ light: 'Bright indirect light' }));

    expect(container.querySelector('.care-info-heading')?.textContent).toBe('Care instructions');
  });
});
