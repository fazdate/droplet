import type { PlantOut } from './api';
import { t } from './i18n';

export type CareSource = 'perenual' | 'llm' | 'default' | 'manual';

export interface CadenceInfo {
  effectiveIntervalDays: number;
  source: CareSource;
}

export interface CadenceEditorHandlers {
  onSetDays: (days: number) => void;
  onReset: () => void;
}

const SOURCE_LABEL_KEYS: Record<CareSource, Parameters<typeof t>[0]> = {
  perenual: 'source.perenual',
  llm: 'source.llm',
  default: 'source.default',
  manual: 'source.manual',
};

/**
 * Plant detail cadence editor — plan section 4.6: "Water every [ N ] days"
 * with +/- steppers, a "Reset to recommended" button (disabled while there's
 * no override), and a label showing where the current number came from.
 */
export function renderCadenceEditor(
  container: HTMLElement,
  plant: PlantOut,
  recommended: CadenceInfo,
  handlers: CadenceEditorHandlers,
): void {
  container.replaceChildren();

  const hasOverride = plant.watering_interval_days_override !== null;
  const currentDays = hasOverride ? plant.watering_interval_days_override! : recommended.effectiveIntervalDays;
  const sourceLabel = t(hasOverride ? SOURCE_LABEL_KEYS.manual : SOURCE_LABEL_KEYS[recommended.source]);

  const wrapper = document.createElement('div');
  wrapper.className = 'cadence-editor';

  const row = document.createElement('div');
  row.className = 'cadence-stepper-row';

  const minusButton = document.createElement('button');
  minusButton.className = 'stepper-minus';
  minusButton.textContent = '−';
  minusButton.setAttribute('aria-label', t('action.decreaseInterval'));
  minusButton.addEventListener('click', () => {
    if (currentDays > 1) handlers.onSetDays(currentDays - 1);
  });
  row.appendChild(minusButton);

  const value = document.createElement('span');
  value.className = 'cadence-value';
  value.textContent = t('cadence.waterEvery', { days: currentDays });
  row.appendChild(value);

  const plusButton = document.createElement('button');
  plusButton.className = 'stepper-plus';
  plusButton.textContent = '+';
  plusButton.setAttribute('aria-label', t('action.increaseInterval'));
  plusButton.addEventListener('click', () => handlers.onSetDays(currentDays + 1));
  row.appendChild(plusButton);

  wrapper.appendChild(row);

  const source = document.createElement('p');
  source.className = 'cadence-source';
  source.textContent = sourceLabel;
  wrapper.appendChild(source);

  const resetButton = document.createElement('button');
  resetButton.className = 'reset-button';
  resetButton.disabled = !hasOverride;
  resetButton.textContent = hasOverride
    ? t('cadence.resetWithDays', { days: recommended.effectiveIntervalDays })
    : t('cadence.reset');
  resetButton.addEventListener('click', () => handlers.onReset());
  wrapper.appendChild(resetButton);

  container.appendChild(wrapper);
}
