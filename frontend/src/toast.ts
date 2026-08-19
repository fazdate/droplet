/** 5-second undo toast — plan section 4.6. Single toast at a time; replaces any prior one. */

import { t } from './i18n';

export function showUndoToast(
  container: HTMLElement,
  message: string,
  onUndo: () => void,
  durationMs = 5000,
): void {
  container.querySelector('.toast')?.remove();

  const toast = document.createElement('div');
  toast.className = 'toast';

  const text = document.createElement('span');
  text.textContent = message;
  toast.appendChild(text);

  const undoButton = document.createElement('button');
  undoButton.className = 'undo-button';
  undoButton.textContent = t('action.undo');
  toast.appendChild(undoButton);

  const timer = setTimeout(() => toast.remove(), durationMs);

  undoButton.addEventListener('click', () => {
    clearTimeout(timer);
    toast.remove();
    onUndo();
  });

  container.appendChild(toast);
}

/** Plain, dismiss-only toast for actions with no undo path (e.g. plant removal). */
export function showToast(container: HTMLElement, message: string, durationMs = 5000): void {
  container.querySelector('.toast')?.remove();

  const toast = document.createElement('div');
  toast.className = 'toast';

  const text = document.createElement('span');
  text.textContent = message;
  toast.appendChild(text);

  setTimeout(() => toast.remove(), durationMs);

  container.appendChild(toast);
}
