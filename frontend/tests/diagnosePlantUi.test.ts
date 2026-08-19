import { describe, expect, it, vi } from 'vitest';
import type { PlantOut } from '../src/api';
import {
  createDiagnoseCaptureInput,
  renderDiagnoseModal,
  renderDiagnosePlantPickerModal,
} from '../src/diagnosePlantUi';

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

describe('renderDiagnoseModal', () => {
  it('should_hide_container_on_idle_step', () => {
    const container = document.createElement('div');
    container.classList.remove('hidden');

    renderDiagnoseModal(container, { step: { name: 'idle' }, plantName: 'Monty', onDismiss: vi.fn() });

    expect(container.classList.contains('hidden')).toBe(true);
    expect(container.innerHTML).toBe('');
  });

  it('should_show_loading_spinner_while_diagnosing', () => {
    const container = document.createElement('div');

    renderDiagnoseModal(container, { step: { name: 'loading' }, plantName: 'Monty', onDismiss: vi.fn() });

    expect(container.classList.contains('hidden')).toBe(false);
    expect(container.querySelector('.spinner')).not.toBeNull();
  });

  it('should_show_healthy_message_when_no_issues_found', () => {
    const container = document.createElement('div');

    renderDiagnoseModal(container, {
      step: { name: 'result', result: { healthy: true, issues: [] } },
      plantName: 'Monty',
      onDismiss: vi.fn(),
    });

    const result = container.querySelector('.diagnose-result');
    expect(result?.textContent).toContain('healthy');
    expect(container.querySelector('.diagnose-issue-list')).toBeNull();
  });

  it('should_list_issues_and_suggestions_when_unhealthy', () => {
    const container = document.createElement('div');

    renderDiagnoseModal(container, {
      step: {
        name: 'result',
        result: {
          healthy: false,
          issues: [
            { issue: 'Yellowing lower leaves', suggestion: 'Water less often.' },
            { issue: 'Small webs on the underside of leaves', suggestion: 'Treat for spider mites.' },
          ],
        },
      },
      plantName: 'Monty',
      onDismiss: vi.fn(),
    });

    const items = container.querySelectorAll('.diagnose-issue');
    expect(items).toHaveLength(2);
    expect(items[0].querySelector('.diagnose-issue-title')?.textContent).toBe('Yellowing lower leaves');
    expect(items[0].querySelector('.diagnose-issue-suggestion')?.textContent).toBe('Water less often.');
    expect(items[1].querySelector('.diagnose-issue-title')?.textContent).toBe('Small webs on the underside of leaves');
  });

  it('should_show_error_message_on_error_step', () => {
    const container = document.createElement('div');

    renderDiagnoseModal(container, {
      step: { name: 'error', message: 'Could not diagnose this photo. Please try again.' },
      plantName: 'Monty',
      onDismiss: vi.fn(),
    });

    expect(container.querySelector('.error-message')?.textContent).toBe(
      'Could not diagnose this photo. Please try again.',
    );
  });

  it('should_call_onDismiss_when_dismiss_button_clicked_after_result', () => {
    const container = document.createElement('div');
    const onDismiss = vi.fn();

    renderDiagnoseModal(container, {
      step: { name: 'result', result: { healthy: true, issues: [] } },
      plantName: 'Monty',
      onDismiss,
    });

    (container.querySelector('.diagnose-dismiss') as HTMLButtonElement).click();

    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it('should_call_onDismiss_when_close_button_clicked_while_loading', () => {
    const container = document.createElement('div');
    const onDismiss = vi.fn();

    renderDiagnoseModal(container, { step: { name: 'loading' }, plantName: 'Monty', onDismiss });

    (container.querySelector('.modal-close') as HTMLButtonElement).click();

    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it('should_not_show_dismiss_button_while_loading', () => {
    const container = document.createElement('div');

    renderDiagnoseModal(container, { step: { name: 'loading' }, plantName: 'Monty', onDismiss: vi.fn() });

    expect(container.querySelector('.diagnose-dismiss')).toBeNull();
  });

  it('should_include_plant_name_in_title', () => {
    const container = document.createElement('div');

    renderDiagnoseModal(container, { step: { name: 'loading' }, plantName: 'Ficus', onDismiss: vi.fn() });

    expect(container.textContent).toContain('Ficus');
  });
});

describe('renderDiagnosePlantPickerModal', () => {
  it('should_hide_container_when_closed', () => {
    const container = document.createElement('div');
    container.classList.remove('hidden');

    renderDiagnosePlantPickerModal(container, {
      open: false,
      plants: [],
      onSelectPlant: vi.fn(),
      onCancel: vi.fn(),
    });

    expect(container.classList.contains('hidden')).toBe(true);
    expect(container.innerHTML).toBe('');
  });

  it('should_list_every_tracked_plant_as_an_option', () => {
    const container = document.createElement('div');

    renderDiagnosePlantPickerModal(container, {
      open: true,
      plants: [plant({ id: 1, nickname: 'Monty' }), plant({ id: 2, nickname: 'Ficus' })],
      onSelectPlant: vi.fn(),
      onCancel: vi.fn(),
    });

    const options = container.querySelectorAll('.room-picker-option');
    expect(options).toHaveLength(2);
    expect(options[0].textContent).toBe('Monty');
    expect(options[1].textContent).toBe('Ficus');
  });

  it('should_call_onSelectPlant_with_the_chosen_plant_id', () => {
    const container = document.createElement('div');
    const onSelectPlant = vi.fn();

    renderDiagnosePlantPickerModal(container, {
      open: true,
      plants: [plant({ id: 7, nickname: 'Monty' })],
      onSelectPlant,
      onCancel: vi.fn(),
    });

    container.querySelector<HTMLButtonElement>('[data-diagnose-plant-option="7"]')?.click();

    expect(onSelectPlant).toHaveBeenCalledWith(7);
  });

  it('should_show_empty_state_when_there_are_no_tracked_plants', () => {
    const container = document.createElement('div');

    renderDiagnosePlantPickerModal(container, { open: true, plants: [], onSelectPlant: vi.fn(), onCancel: vi.fn() });

    expect(container.querySelector('.room-picker-list')).toBeNull();
    expect(container.textContent).toContain('add one first');
  });

  it('should_call_onCancel_when_close_button_clicked', () => {
    const container = document.createElement('div');
    const onCancel = vi.fn();

    renderDiagnosePlantPickerModal(container, { open: true, plants: [], onSelectPlant: vi.fn(), onCancel });

    (container.querySelector('.modal-close') as HTMLButtonElement).click();

    expect(onCancel).toHaveBeenCalledOnce();
  });
});

describe('createDiagnoseCaptureInput', () => {
  it('should_be_a_hidden_file_input_that_accepts_images', () => {
    const input = createDiagnoseCaptureInput(vi.fn());

    expect(input.type).toBe('file');
    expect(input.accept).toBe('image/*');
    expect(input.style.display).toBe('none');
  });

  it('should_call_onFileSelected_with_the_chosen_file_and_reset_the_input', () => {
    const onFileSelected = vi.fn();
    const input = createDiagnoseCaptureInput(onFileSelected);
    const file = new File(['fake'], 'issue.jpg', { type: 'image/jpeg' });
    Object.defineProperty(input, 'files', { value: [file] });

    input.dispatchEvent(new Event('change'));

    expect(onFileSelected).toHaveBeenCalledWith(file);
    expect(input.value).toBe('');
  });

  it('should_not_call_onFileSelected_when_the_picker_is_cancelled', () => {
    const onFileSelected = vi.fn();
    const input = createDiagnoseCaptureInput(onFileSelected);
    Object.defineProperty(input, 'files', { value: [] });

    input.dispatchEvent(new Event('change'));

    expect(onFileSelected).not.toHaveBeenCalled();
  });
});
