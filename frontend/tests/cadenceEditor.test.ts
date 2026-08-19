import { describe, expect, it, vi } from 'vitest';
import { renderCadenceEditor } from '../src/cadenceEditor';
import type { PlantOut } from '../src/api';

function plant(overrides: Partial<PlantOut> = {}): PlantOut {
  return {
    id: 1,
    nickname: 'Basil',
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
    ...overrides,
  };
}

describe('renderCadenceEditor', () => {
  it('should_show_recommended_source_label_when_no_override', () => {
    const container = document.createElement('div');

    renderCadenceEditor(container, plant(), { effectiveIntervalDays: 7, source: 'perenual' }, { onSetDays: vi.fn(), onReset: vi.fn() });

    expect(container.textContent).toContain('recommended (Perenual)');
  });

  it('should_show_set_by_you_label_when_override_present', () => {
    const container = document.createElement('div');

    renderCadenceEditor(
      container,
      plant({ watering_interval_days_override: 10 }),
      { effectiveIntervalDays: 10, source: 'perenual' },
      { onSetDays: vi.fn(), onReset: vi.fn() },
    );

    expect(container.textContent).toContain('set by you');
  });

  it('should_disable_reset_button_when_no_override', () => {
    const container = document.createElement('div');

    renderCadenceEditor(container, plant(), { effectiveIntervalDays: 7, source: 'llm' }, { onSetDays: vi.fn(), onReset: vi.fn() });

    const resetButton = container.querySelector<HTMLButtonElement>('.reset-button')!;
    expect(resetButton.disabled).toBe(true);
  });

  it('should_enable_reset_button_and_show_recommended_value_when_override_present', () => {
    const container = document.createElement('div');

    renderCadenceEditor(
      container,
      plant({ watering_interval_days_override: 10 }),
      { effectiveIntervalDays: 7, source: 'default' },
      { onSetDays: vi.fn(), onReset: vi.fn() },
    );

    const resetButton = container.querySelector<HTMLButtonElement>('.reset-button')!;
    expect(resetButton.disabled).toBe(false);
    expect(resetButton.textContent).toContain('7 days');
  });

  it('should_increment_days_via_stepper_and_call_onSetDays', () => {
    const container = document.createElement('div');
    const onSetDays = vi.fn();

    renderCadenceEditor(container, plant(), { effectiveIntervalDays: 7, source: 'perenual' }, { onSetDays, onReset: vi.fn() });

    container.querySelector<HTMLButtonElement>('.stepper-plus')?.click();

    expect(onSetDays).toHaveBeenCalledWith(8);
  });

  it('should_decrement_days_via_stepper_and_call_onSetDays', () => {
    const container = document.createElement('div');
    const onSetDays = vi.fn();

    renderCadenceEditor(container, plant(), { effectiveIntervalDays: 7, source: 'perenual' }, { onSetDays, onReset: vi.fn() });

    container.querySelector<HTMLButtonElement>('.stepper-minus')?.click();

    expect(onSetDays).toHaveBeenCalledWith(6);
  });

  it('should_not_decrement_below_1_day', () => {
    const container = document.createElement('div');
    const onSetDays = vi.fn();

    renderCadenceEditor(
      container,
      plant({ watering_interval_days_override: 1 }),
      { effectiveIntervalDays: 1, source: 'manual' },
      { onSetDays, onReset: vi.fn() },
    );

    container.querySelector<HTMLButtonElement>('.stepper-minus')?.click();

    expect(onSetDays).not.toHaveBeenCalled();
  });

  it('should_call_onReset_when_reset_button_clicked', () => {
    const container = document.createElement('div');
    const onReset = vi.fn();

    renderCadenceEditor(
      container,
      plant({ watering_interval_days_override: 10 }),
      { effectiveIntervalDays: 7, source: 'perenual' },
      { onSetDays: vi.fn(), onReset },
    );

    container.querySelector<HTMLButtonElement>('.reset-button')?.click();

    expect(onReset).toHaveBeenCalled();
  });
});
