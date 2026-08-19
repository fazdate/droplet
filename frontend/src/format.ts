/** Pure formatting helpers — no DOM, no fetch, easy to unit test. */

import { t } from './i18n';

function startOfUtcDay(date: Date): number {
  return Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
}

/** Human-readable due status for a plant tile, e.g. "Water today", "2 days late", "in 3 days". */
export function dueLabel(nextDueAtIso: string | null, now: Date): string {
  if (nextDueAtIso === null) {
    return t('due.notScheduled');
  }

  const nextDue = new Date(nextDueAtIso);
  const diffDays = Math.round((startOfUtcDay(now) - startOfUtcDay(nextDue)) / 86_400_000);

  if (diffDays === 0) {
    return t('due.today');
  }
  if (diffDays > 0) {
    return diffDays === 1 ? t('due.lateOne') : t('due.lateMany', { count: diffDays });
  }
  const inDays = -diffDays;
  return inDays === 1 ? t('due.inOne') : t('due.inMany', { count: inDays });
}
