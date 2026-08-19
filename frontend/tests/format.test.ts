import { describe, expect, it } from 'vitest';
import { dueLabel } from '../src/format';

describe('dueLabel', () => {
  const now = new Date('2026-08-17T09:00:00Z');

  it('should_show_water_today_when_due_today', () => {
    expect(dueLabel('2026-08-17T09:00:00Z', now)).toBe('Water today');
  });

  it('should_show_water_today_when_due_earlier_today', () => {
    expect(dueLabel('2026-08-17T02:00:00Z', now)).toBe('Water today');
  });

  it('should_show_days_late_when_overdue', () => {
    expect(dueLabel('2026-08-14T09:00:00Z', now)).toBe('3 days late');
  });

  it('should_show_singular_day_late', () => {
    expect(dueLabel('2026-08-16T09:00:00Z', now)).toBe('1 day late');
  });

  it('should_show_in_n_days_when_due_in_future', () => {
    expect(dueLabel('2026-08-20T09:00:00Z', now)).toBe('in 3 days');
  });

  it('should_show_in_1_day_singular', () => {
    expect(dueLabel('2026-08-18T09:00:00Z', now)).toBe('in 1 day');
  });

  it('should_show_not_scheduled_when_next_due_is_null', () => {
    expect(dueLabel(null, now)).toBe('not scheduled');
  });
});
