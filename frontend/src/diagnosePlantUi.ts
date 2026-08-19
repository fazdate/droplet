import type { DiagnoseResponse, PlantOut } from './api';
import { createModalCloseButton } from './addPlantUi';
import { t } from './i18n';

export type DiagnoseStep =
  | { name: 'idle' }
  | { name: 'loading' }
  | { name: 'result'; result: DiagnoseResponse }
  | { name: 'error'; message: string };

export interface DiagnoseModalOptions {
  step: DiagnoseStep;
  plantName: string;
  onDismiss: () => void;
}

/**
 * "Diagnose plant issue" (TODO.md: "Recognize issues with the plants...
 * provide suggestions for how to fix them"), triggered from the bottom-right
 * quick-actions button (see addPlantUi.ts's chooser) rather than a specific
 * plant tile's "⋮" menu — picking which tracked plant a photo is for is an
 * explicit step (renderDiagnosePlantPickerModal below) so there's no risk of
 * diagnosing the wrong plant just because a different tile happened to be
 * expanded. This modal renders the loading/result/error states once a plant
 * has been picked and a photo captured (see createDiagnoseCaptureInput).
 */
export function renderDiagnoseModal(container: HTMLElement, options: DiagnoseModalOptions): void {
  container.replaceChildren();
  const { step } = options;
  if (step.name === 'idle') {
    container.classList.add('hidden');
    return;
  }
  container.classList.remove('hidden');

  const modal = document.createElement('div');
  modal.className = 'add-plant-modal diagnose-modal';
  modal.appendChild(createModalCloseButton(() => options.onDismiss()));

  const title = document.createElement('p');
  title.textContent = t('diagnose.title', { name: options.plantName });
  modal.appendChild(title);

  if (step.name === 'loading') {
    modal.appendChild(renderLoadingStep());
  } else if (step.name === 'result') {
    modal.appendChild(renderResultStep(step.result));
  } else if (step.name === 'error') {
    const p = document.createElement('p');
    p.className = 'error-message';
    p.textContent = step.message;
    modal.appendChild(p);
  }

  if (step.name === 'result' || step.name === 'error') {
    const dismissButton = document.createElement('button');
    dismissButton.type = 'button';
    dismissButton.className = 'diagnose-dismiss';
    dismissButton.textContent = t('diagnose.done');
    dismissButton.addEventListener('click', () => options.onDismiss());
    modal.appendChild(dismissButton);
  }

  container.appendChild(modal);
}

function renderLoadingStep(): HTMLElement {
  const wrapper = document.createElement('div');
  wrapper.className = 'identifying-step';

  const spinner = document.createElement('div');
  spinner.className = 'spinner';
  spinner.setAttribute('aria-hidden', 'true');
  wrapper.appendChild(spinner);

  const p = document.createElement('p');
  p.textContent = t('diagnose.loading');
  wrapper.appendChild(p);

  return wrapper;
}

function renderResultStep(result: DiagnoseResponse): HTMLElement {
  const wrapper = document.createElement('div');
  wrapper.className = 'diagnose-result';

  if (result.healthy || result.issues.length === 0) {
    const p = document.createElement('p');
    p.textContent = t('diagnose.healthy');
    wrapper.appendChild(p);
    return wrapper;
  }

  const list = document.createElement('ul');
  list.className = 'diagnose-issue-list';
  for (const { issue, suggestion } of result.issues) {
    const item = document.createElement('li');
    item.className = 'diagnose-issue';

    const issueLabel = document.createElement('p');
    issueLabel.className = 'diagnose-issue-title';
    issueLabel.textContent = issue;
    item.appendChild(issueLabel);

    const suggestionLabel = document.createElement('p');
    suggestionLabel.className = 'diagnose-issue-suggestion';
    suggestionLabel.textContent = suggestion;
    item.appendChild(suggestionLabel);

    list.appendChild(item);
  }
  wrapper.appendChild(list);

  return wrapper;
}

export interface DiagnosePlantPickerOptions {
  open: boolean;
  plants: PlantOut[];
  onSelectPlant: (plantId: number) => void;
  onCancel: () => void;
}

/**
 * "Which plant is this for?" step of the diagnose flow — shown after picking
 * "Diagnose plant issue" from the quick-actions chooser (addPlantUi.ts) and
 * before the camera opens, so the user consciously picks the plant instead of
 * it being implied by whichever tile they'd expanded (the confusing old
 * "⋮" menu entry point this replaces). Reuses the same list/option styling as
 * moveRoomUi.ts's room picker.
 */
export function renderDiagnosePlantPickerModal(container: HTMLElement, options: DiagnosePlantPickerOptions): void {
  container.replaceChildren();
  if (!options.open) {
    container.classList.add('hidden');
    return;
  }
  container.classList.remove('hidden');

  const modal = document.createElement('div');
  modal.className = 'add-plant-modal room-picker-modal';
  modal.appendChild(createModalCloseButton(() => options.onCancel()));

  const title = document.createElement('p');
  title.textContent = t('diagnose.pickPlantPrompt');
  modal.appendChild(title);

  if (options.plants.length === 0) {
    const empty = document.createElement('p');
    empty.textContent = t('diagnose.noPlantsYet');
    modal.appendChild(empty);
  } else {
    const list = document.createElement('div');
    list.className = 'room-picker-list';

    for (const plant of options.plants) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'room-picker-option';
      button.textContent = plant.nickname;
      button.dataset.diagnosePlantOption = String(plant.id);
      button.addEventListener('click', () => options.onSelectPlant(plant.id));
      list.appendChild(button);
    }

    modal.appendChild(list);
  }

  container.appendChild(modal);
}

/**
 * Hidden file input used to capture/select the photo once a plant has
 * already been chosen in renderDiagnosePlantPickerModal above — kept as its
 * own standalone element (main.ts appends it once and calls `.click()` after
 * a plant is picked) rather than one-per-tile like the old "⋮" menu control,
 * since selection now happens before the photo is taken.
 */
export function createDiagnoseCaptureInput(onFileSelected: (file: File) => void): HTMLInputElement {
  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.setAttribute('capture', 'environment');
  input.style.display = 'none';

  input.addEventListener('change', () => {
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    onFileSelected(file);
  });

  return input;
}
