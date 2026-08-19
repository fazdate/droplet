import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { showToast, showUndoToast } from '../src/toast';

describe('showUndoToast', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should_render_message_and_undo_button', () => {
    const container = document.createElement('div');

    showUndoToast(container, 'Watered Basil', vi.fn());

    expect(container.textContent).toContain('Watered Basil');
    expect(container.querySelector('.undo-button')).not.toBeNull();
  });

  it('should_call_onUndo_and_remove_toast_when_undo_clicked', () => {
    const container = document.createElement('div');
    const onUndo = vi.fn();

    showUndoToast(container, 'Watered Basil', onUndo);
    container.querySelector<HTMLButtonElement>('.undo-button')?.click();

    expect(onUndo).toHaveBeenCalledOnce();
    expect(container.querySelector('.toast')).toBeNull();
  });

  it('should_auto_dismiss_after_5_seconds_without_calling_onUndo', () => {
    const container = document.createElement('div');
    const onUndo = vi.fn();

    showUndoToast(container, 'Watered Basil', onUndo, 5000);
    vi.advanceTimersByTime(5000);

    expect(onUndo).not.toHaveBeenCalled();
    expect(container.querySelector('.toast')).toBeNull();
  });

  it('should_replace_an_existing_toast_with_a_new_one', () => {
    const container = document.createElement('div');

    showUndoToast(container, 'First', vi.fn());
    showUndoToast(container, 'Second', vi.fn());

    expect(container.querySelectorAll('.toast').length).toBe(1);
    expect(container.textContent).toContain('Second');
  });
});

describe('showToast', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('should_render_message_without_undo_button', () => {
    const container = document.createElement('div');

    showToast(container, 'Basil removed');

    expect(container.textContent).toContain('Basil removed');
    expect(container.querySelector('.undo-button')).toBeNull();
  });

  it('should_auto_dismiss_after_the_given_duration', () => {
    const container = document.createElement('div');

    showToast(container, 'Basil removed', 5000);
    vi.advanceTimersByTime(5000);

    expect(container.querySelector('.toast')).toBeNull();
  });

  it('should_replace_an_existing_toast_with_a_new_one', () => {
    const container = document.createElement('div');

    showToast(container, 'First');
    showToast(container, 'Second');

    expect(container.querySelectorAll('.toast').length).toBe(1);
    expect(container.textContent).toContain('Second');
  });
});
