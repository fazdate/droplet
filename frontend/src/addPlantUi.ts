import type { IdentifyCandidate, RoomSummary } from './api';
import { t } from './i18n';

export type AddPlantStep =
  | { name: 'idle' }
  | { name: 'identifying' }
  | { name: 'candidates'; photoId: string; candidates: IdentifyCandidate[] }
  | { name: 'manual'; photoId: string }
  | { name: 'nickname-prompt'; photoId: string; species_id: number; defaultName: string }
  | { name: 'room-picker'; photoId: string; species_id: number; nickname?: string }
  | { name: 'error'; message: string; photoId?: string };

export interface AddPlantModalHandlers {
  rooms: RoomSummary[];
  onFileSelected: (file: File) => void;
  onAcceptCandidate: (candidate: IdentifyCandidate) => void;
  onRejectAll: () => void;
  onSearchByName: (query: string) => Promise<IdentifyCandidate[]>;
  onManualSubmit: (name: string, days: number) => void;
  onSkipNickname: () => void;
  onSetNickname: (nickname: string) => void;
  onRoomSubmit: (choice: { roomId: number } | { newRoomName: string }) => void;
  onRetry: () => void;
  onUseManual: () => void;
  onCancel: () => void;
}

const INTERVAL_SHORTCUTS: Array<[label: string, days: number]> = [
  [t('interval.every4Days'), 4],
  [t('interval.weekly'), 7],
  [t('interval.every2Weeks'), 14],
];

export function createModalCloseButton(onCancel: () => void): HTMLButtonElement {
  const closeButton = document.createElement('button');
  closeButton.type = 'button';
  closeButton.className = 'modal-close';
  closeButton.textContent = '×';
  closeButton.setAttribute('aria-label', t('action.cancel'));
  closeButton.title = t('action.cancel');
  closeButton.addEventListener('click', onCancel);
  return closeButton;
}

export interface NicknameModalOptions {
  title: string;
  currentNickname: string;
  onSubmit: (nickname: string) => void;
  onCancel: () => void;
}

export interface TextPromptModalOptions {
  title: string;
  currentValue: string;
  placeholder: string;
  submitLabel: string;
  onSubmit: (value: string) => void;
  onCancel: () => void;
  valueClassName?: string;
  submitClassName?: string;
  showCancelButton?: boolean;
}

export function renderTextPromptModal(container: HTMLElement, options: TextPromptModalOptions): void {
  container.replaceChildren();
  container.classList.remove('hidden');

  const modal = document.createElement('div');
  modal.className = 'add-plant-modal text-prompt-modal';
  modal.appendChild(createModalCloseButton(options.onCancel));

  const title = document.createElement('p');
  title.textContent = options.title;
  modal.appendChild(title);

  const form = document.createElement('form');
  form.className = 'text-prompt-form';

  const input = document.createElement('input');
  input.type = 'text';
  input.className = options.valueClassName ?? 'text-prompt-input';
  input.placeholder = options.placeholder;
  input.setAttribute('aria-label', options.placeholder);
  input.value = options.currentValue;
  form.appendChild(input);

  const buttonRow = document.createElement('div');
  buttonRow.className = 'button-row';

  if (options.showCancelButton !== false) {
    const cancelButton = document.createElement('button');
    cancelButton.type = 'button';
    cancelButton.className = 'text-prompt-cancel';
    cancelButton.textContent = t('action.cancel');
    cancelButton.addEventListener('click', options.onCancel);
    buttonRow.appendChild(cancelButton);
  }

  const submit = document.createElement('button');
  submit.type = 'submit';
  submit.className = options.submitClassName ?? 'text-prompt-submit';
  submit.textContent = options.submitLabel;
  buttonRow.appendChild(submit);

  form.appendChild(buttonRow);

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const value = input.value.trim();
    if (!value) return;
    options.onSubmit(value);
  });

  modal.appendChild(form);
  container.appendChild(modal);
}

export function renderNicknameEditorModal(container: HTMLElement, options: NicknameModalOptions): void {
  renderTextPromptModal(container, {
    title: options.title,
    currentValue: options.currentNickname,
    placeholder: t('nickname.placeholder'),
    submitLabel: t('action.updateNickname'),
    onSubmit: options.onSubmit,
    onCancel: options.onCancel,
    valueClassName: 'nickname-editor-input',
    submitClassName: 'nickname-editor-submit',
  });
}

/**
 * Persisted (survives a page reload, unlike a plain JS variable) marker for
 * "the native camera app was launched and we're waiting for it to hand a
 * photo back". See `consumeInterruptedCapture` below for why this exists.
 */
const PENDING_CAPTURE_KEY = 'droplet:pendingPhotoCapture';

function markCaptureStarted(): void {
  try {
    sessionStorage.setItem(PENDING_CAPTURE_KEY, '1');
  } catch {
    // sessionStorage can throw (e.g. private-browsing storage limits) — the
    // capture-interrupted detection just becomes a no-op, nothing else breaks.
  }
}

function clearCaptureMarker(): void {
  try {
    sessionStorage.removeItem(PENDING_CAPTURE_KEY);
  } catch {
    // ignore, see markCaptureStarted
  }
}

/**
 * Fix for TODO.md: launching the native Camera app is memory-heavy, and
 * while our tab is backgrounded for the capture, Android can kill and then
 * reload our page to reclaim memory (the "memory" notice some users see at
 * the bottom of the screen). That reload wipes all in-page JS state before
 * the captured photo ever reaches us, so the add-plant flow silently never
 * starts — indistinguishable, from the user's side, from "nothing happened".
 * There is no way to recover the actual photo once the page has reloaded,
 * but we *can* detect that this happened (the marker set by
 * `markCaptureStarted` survives the reload in sessionStorage) and tell the
 * user clearly instead of leaving them puzzled. Call this once at startup.
 */
export function consumeInterruptedCapture(): boolean {
  try {
    if (sessionStorage.getItem(PENDING_CAPTURE_KEY) !== '1') return false;
    sessionStorage.removeItem(PENDING_CAPTURE_KEY);
    return true;
  } catch {
    return false;
  }
}

export function renderAddButton(
  container: HTMLElement,
  choiceContainer: HTMLElement,
  handlers: { onFileSelected: (file: File) => void; onChooseRoom: () => void; onChooseDiagnose: () => void },
): void {
  const button = document.createElement('button');
  button.className = 'add-plant-button';
  // No longer a plain "add" affordance now that the chooser also offers
  // "Diagnose plant issue" (TODO.md) — generic "Quick actions" label/icon
  // (a sparkle, hinting at the AI-assisted actions) instead of "+"/"Add plant".
  button.setAttribute('aria-label', t('action.quickActions'));
  button.title = t('action.quickActions');

  const symbol = document.createElement('span');
  symbol.className = 'add-plant-button-symbol';
  symbol.appendChild(createQuickActionsIcon());
  button.appendChild(symbol);

  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.setAttribute('capture', 'environment');
  input.style.display = 'none';

  // Handles a captured/selected photo exactly once, then clears the input so
  // it's ready for the next capture and so a re-run of this function (e.g.
  // the window 'focus' fallback below) is a harmless no-op once handled.
  function handlePickedFile(): void {
    const file = input.files?.[0];
    // Reaching here at all (this JS context is alive to run it) means no
    // reload happened for this attempt, whether a file came back or the
    // picker was cancelled — either way there's nothing "interrupted" to flag.
    clearCaptureMarker();
    if (!file) return;
    input.value = '';
    handlers.onFileSelected(file);
  }

  input.addEventListener('change', handlePickedFile);

  // Fix for TODO.md: on some Android browsers (observed on Brave/Samsung)
  // the camera app occasionally hands the photo back to the page without
  // the input's 'change' event ever firing — the file is sitting on
  // `input.files`, but nothing tells us so, so the identify flow silently
  // never starts until a second photo is taken. Re-checking `input.files`
  // when the window regains focus (i.e. the user has returned from the
  // camera/file picker) catches that dropped event.
  window.addEventListener('focus', handlePickedFile);

  function startPlantCapture(): void {
    markCaptureStarted();
    input.click();
  }

  function hideChoice(): void {
    renderAddChoiceModal(choiceContainer, {
      open: false,
      onChoosePlant: startPlantCapture,
      onChooseRoom: handlers.onChooseRoom,
      onChooseDiagnose: handlers.onChooseDiagnose,
      onCancel: hideChoice,
    });
  }

  button.addEventListener('click', () => {
    renderAddChoiceModal(choiceContainer, {
      open: true,
      onChoosePlant: () => {
        hideChoice();
        startPlantCapture();
      },
      onChooseRoom: () => {
        hideChoice();
        handlers.onChooseRoom();
      },
      onChooseDiagnose: () => {
        hideChoice();
        handlers.onChooseDiagnose();
      },
      onCancel: hideChoice,
    });
  });

  container.appendChild(button);
  container.appendChild(input);
}

export function renderAddChoiceModal(
  container: HTMLElement,
  options: {
    open: boolean;
    onChoosePlant: () => void;
    onChooseRoom: () => void;
    onChooseDiagnose: () => void;
    onCancel: () => void;
  },
): void {
  container.replaceChildren();
  if (!options.open) {
    container.classList.add('hidden');
    return;
  }

  container.classList.remove('hidden');
  const modal = document.createElement('div');
  modal.className = 'add-plant-modal add-choice-modal';
  modal.appendChild(createModalCloseButton(options.onCancel));

  const title = document.createElement('p');
  title.textContent = t('chooser.title');
  modal.appendChild(title);

  const plantButton = document.createElement('button');
  plantButton.type = 'button';
  plantButton.textContent = t('action.addPlant');
  plantButton.dataset.addChoicePlant = '1';
  plantButton.addEventListener('click', options.onChoosePlant);
  modal.appendChild(plantButton);

  const roomButton = document.createElement('button');
  roomButton.type = 'button';
  roomButton.textContent = t('action.addRoom');
  roomButton.dataset.addChoiceRoom = '1';
  roomButton.addEventListener('click', options.onChooseRoom);
  modal.appendChild(roomButton);

  // "Diagnose plant issue" (TODO.md), moved here from the per-plant "⋮" menu
  // — picking which tracked plant a photo is for is now an explicit step of
  // this flow (see diagnosePlantUi.ts's plant-picker modal) rather than being
  // implied by which plant tile happened to be expanded, which could easily
  // end up diagnosing the wrong plant.
  const diagnoseButton = document.createElement('button');
  diagnoseButton.type = 'button';
  diagnoseButton.textContent = t('action.diagnose');
  diagnoseButton.dataset.addChoiceDiagnose = '1';
  diagnoseButton.addEventListener('click', options.onChooseDiagnose);
  modal.appendChild(diagnoseButton);

  container.appendChild(modal);
}

export function renderAddPlantModal(container: HTMLElement, step: AddPlantStep, handlers: AddPlantModalHandlers): void {
  container.replaceChildren();
  if (step.name === 'idle') {
    container.classList.add('hidden');
    return;
  }
  container.classList.remove('hidden');

  const modal = document.createElement('div');
  modal.className = 'add-plant-modal';

  modal.appendChild(createModalCloseButton(() => handlers.onCancel()));

  if (step.name === 'identifying') {
    modal.appendChild(renderIdentifyingStep());
  } else if (step.name === 'candidates') {
    modal.appendChild(renderCandidatesStep(step.candidates, handlers));
  } else if (step.name === 'manual') {
    modal.appendChild(renderManualStep(handlers));
  } else if (step.name === 'nickname-prompt') {
    modal.appendChild(renderNicknamePromptStep(step, handlers));
  } else if (step.name === 'room-picker') {
    modal.appendChild(renderRoomPickerStep(handlers));
  } else if (step.name === 'error') {
    const wrapper = document.createElement('div');
    wrapper.className = 'error-step';

    const p = document.createElement('p');
    p.className = 'error-message';
    p.textContent = step.message;
    wrapper.appendChild(p);

    const buttonRow = document.createElement('div');
    buttonRow.className = 'button-row';

    if (step.photoId) {
      const retryButton = document.createElement('button');
      retryButton.type = 'button';
      retryButton.className = 'error-retry-button';
      retryButton.textContent = t('action.tryAgain');
      retryButton.addEventListener('click', handlers.onRetry);
      buttonRow.appendChild(retryButton);
    } else {
      const manualButton = document.createElement('button');
      manualButton.type = 'button';
      manualButton.className = 'error-manual-button';
      manualButton.textContent = t('action.addManually');
      manualButton.addEventListener('click', handlers.onUseManual);
      buttonRow.appendChild(manualButton);
    }

    const cancelButton = document.createElement('button');
    cancelButton.type = 'button';
    cancelButton.className = 'error-cancel-button';
    cancelButton.textContent = t('action.cancel');
    cancelButton.addEventListener('click', handlers.onCancel);
    buttonRow.appendChild(cancelButton);

    wrapper.appendChild(buttonRow);
    modal.appendChild(wrapper);
  }

  container.appendChild(modal);
}

function renderIdentifyingStep(): HTMLElement {
  const wrapper = document.createElement('div');
  wrapper.className = 'identifying-step';

  const spinner = document.createElement('div');
  spinner.className = 'spinner';
  spinner.setAttribute('aria-hidden', 'true');
  wrapper.appendChild(spinner);

  const p = document.createElement('p');
  p.textContent = t('modal.identifying');
  wrapper.appendChild(p);

  return wrapper;
}

function renderCandidatesStep(candidates: IdentifyCandidate[], handlers: AddPlantModalHandlers): HTMLElement {
  const wrapper = document.createElement('div');
  const [top, ...rest] = candidates;

  const question = document.createElement('p');
  question.textContent = t('modal.isThis', { name: top.common_name ?? top.scientific_name });
  wrapper.appendChild(question);

  if (top.reference_image_url) {
    const img = document.createElement('img');
    img.src = top.reference_image_url;
    img.alt = top.scientific_name;
    wrapper.appendChild(img);
  }

  const buttonRow = document.createElement('div');
  buttonRow.className = 'button-row';

  const yesButton = document.createElement('button');
  yesButton.className = 'candidate-yes';
  yesButton.textContent = t('action.yes');
  yesButton.addEventListener('click', () => handlers.onAcceptCandidate(top));
  buttonRow.appendChild(yesButton);

  const noButton = document.createElement('button');
  noButton.className = 'candidate-no';
  noButton.textContent = t('action.no');
  noButton.addEventListener('click', () => handlers.onRejectAll());
  buttonRow.appendChild(noButton);

  wrapper.appendChild(buttonRow);

  if (rest.length > 0) {
    const otherList = document.createElement('ul');
    otherList.className = 'other-candidates';
    for (const candidate of rest) {
      const li = document.createElement('li');
      const button = document.createElement('button');
      button.className = 'other-candidate';
      button.addEventListener('click', () => handlers.onAcceptCandidate(candidate));

      if (candidate.reference_image_url) {
        const img = document.createElement('img');
        img.className = 'other-candidate-thumb';
        img.src = candidate.reference_image_url;
        img.alt = candidate.scientific_name;
        button.appendChild(img);
      }

      const label = document.createElement('span');
      label.textContent = candidate.common_name ?? candidate.scientific_name;
      button.appendChild(label);

      li.appendChild(button);
      otherList.appendChild(li);
    }
    wrapper.appendChild(otherList);
  }

  return wrapper;
}

function renderManualStep(handlers: AddPlantModalHandlers): HTMLElement {
  const wrapper = document.createElement('div');

  const searchLabel = document.createElement('p');
  searchLabel.textContent = t('manual.searchPrompt');
  wrapper.appendChild(searchLabel);

  // The name input lives outside the manual-creation <form> below but is
  // shared by both paths: searching by name, and (if there's no match)
  // falling back to manual creation using whatever was typed here.
  const nameInput = document.createElement('input');
  nameInput.type = 'text';
  nameInput.placeholder = t('manual.namePlaceholder');
  nameInput.className = 'manual-name-input';
  wrapper.appendChild(nameInput);

  const searchButton = document.createElement('button');
  searchButton.type = 'button';
  searchButton.className = 'manual-search-button';
  searchButton.textContent = t('action.search');
  wrapper.appendChild(searchButton);

  const resultsList = document.createElement('ul');
  resultsList.className = 'search-results';
  wrapper.appendChild(resultsList);

  searchButton.addEventListener('click', () => {
    const query = nameInput.value.trim();
    if (!query) return;

    // Give immediate feedback that the search is running — otherwise the UI
    // looks frozen while we wait on the network round-trip.
    resultsList.replaceChildren();
    searchButton.disabled = true;
    searchButton.classList.add('is-searching');

    const loadingItem = document.createElement('li');
    loadingItem.className = 'search-loading';
    const spinner = document.createElement('span');
    spinner.className = 'spinner spinner-small';
    spinner.setAttribute('aria-hidden', 'true');
    loadingItem.appendChild(spinner);
    const loadingText = document.createElement('span');
    loadingText.textContent = t('manual.searching');
    loadingItem.appendChild(loadingText);
    resultsList.appendChild(loadingItem);

    handlers
      .onSearchByName(query)
      .then((results) => {
        resultsList.replaceChildren();
        if (results.length === 0) {
          const li = document.createElement('li');
          li.className = 'search-no-results';
          li.textContent = t('manual.noResults');
          resultsList.appendChild(li);
          return;
        }
        for (const result of results) {
          const li = document.createElement('li');
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'search-result-button';
          button.textContent = result.common_name ?? result.scientific_name;
          button.addEventListener('click', () => handlers.onAcceptCandidate(result));
          li.appendChild(button);
          resultsList.appendChild(li);
        }
      })
      .finally(() => {
        searchButton.disabled = false;
        searchButton.classList.remove('is-searching');
      });
  });

  const divider = document.createElement('p');
  divider.className = 'manual-divider';
  divider.textContent = t('manual.divider');
  wrapper.appendChild(divider);

  const form = document.createElement('form');
  form.className = 'manual-species-form';

  const daysInput = document.createElement('input');
  daysInput.type = 'range';
  daysInput.min = '1';
  daysInput.max = '60';
  daysInput.value = '7';
  daysInput.className = 'manual-days-input';
  form.appendChild(daysInput);

  const chips = document.createElement('div');
  chips.className = 'interval-shortcuts';
  for (const [label, days] of INTERVAL_SHORTCUTS) {
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.textContent = label;
    chip.addEventListener('click', () => {
      daysInput.value = String(days);
    });
    chips.appendChild(chip);
  }
  form.appendChild(chips);

  const submit = document.createElement('button');
  submit.type = 'submit';
  submit.textContent = t('action.addPlant');
  form.appendChild(submit);

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    handlers.onManualSubmit(nameInput.value, Number(daysInput.value));
  });

  wrapper.appendChild(form);

  return wrapper;
}

function renderNicknamePromptStep(
  step: Extract<AddPlantStep, { name: 'nickname-prompt' }>,
  handlers: AddPlantModalHandlers,
): HTMLElement {
  const wrapper = document.createElement('div');
  wrapper.className = 'nickname-prompt-step';

  const question = document.createElement('p');
  question.textContent = t('nickname.prompt', { name: step.defaultName });
  wrapper.appendChild(question);

  const form = document.createElement('form');
  form.className = 'nickname-form';

  const nicknameInput = document.createElement('input');
  nicknameInput.type = 'text';
  nicknameInput.className = 'nickname-input';
  nicknameInput.placeholder = t('nickname.placeholder');
  nicknameInput.setAttribute('aria-label', t('nickname.placeholder'));
  nicknameInput.style.display = 'none';
  form.appendChild(nicknameInput);

  const buttonRow = document.createElement('div');
  buttonRow.className = 'button-row';

  const yesButton = document.createElement('button');
  yesButton.type = 'button';
  yesButton.className = 'nickname-yes';
  yesButton.textContent = t('action.yes');
  buttonRow.appendChild(yesButton);

  const noButton = document.createElement('button');
  noButton.type = 'button';
  noButton.className = 'nickname-no';
  noButton.textContent = t('action.no');
  noButton.addEventListener('click', () => handlers.onSkipNickname());
  buttonRow.appendChild(noButton);

  form.appendChild(buttonRow);

  const submit = document.createElement('button');
  submit.type = 'submit';
  submit.className = 'nickname-submit';
  submit.textContent = t('action.continue');
  submit.style.display = 'none';
  form.appendChild(submit);

  // Revealing the input+submit only after "Yes" keeps the common (no
  // nickname) path a single tap, per TODO.md: a separate prompt asking
  // whether a custom nickname is wanted, rather than always showing an input.
  yesButton.addEventListener('click', () => {
    nicknameInput.style.display = '';
    submit.style.display = '';
    yesButton.style.display = 'none';
    noButton.style.display = 'none';
    nicknameInput.focus();
  });

  form.addEventListener('submit', (event) => {
    event.preventDefault();
    handlers.onSetNickname(nicknameInput.value);
  });

  wrapper.appendChild(form);
  return wrapper;
}

function renderRoomPickerStep(handlers: AddPlantModalHandlers): HTMLElement {
  const form = document.createElement('form');
  form.className = 'room-picker-form';
  const hasExistingRooms = handlers.rooms.length > 0;

  if (!hasExistingRooms) {
   const note = document.createElement('p');
   note.className = 'room-picker-empty-note';
   note.textContent = t('roomPicker.noRoomsYet');
   form.appendChild(note);
  }

  let roomSelect: HTMLSelectElement | null = null;
  if (hasExistingRooms) {
   roomSelect = document.createElement('select');
   roomSelect.className = 'room-select';
   for (const room of handlers.rooms) {
     const option = document.createElement('option');
     option.value = String(room.id);
     option.textContent = room.name;
     roomSelect.appendChild(option);
   }
   const newOption = document.createElement('option');
   newOption.value = 'new';
   newOption.textContent = t('roomPicker.newRoomOption');
   roomSelect.appendChild(newOption);
   form.appendChild(roomSelect);
  }

  const newRoomInput = document.createElement('input');
  newRoomInput.type = 'text';
  newRoomInput.className = 'new-room-input';
  newRoomInput.placeholder = t('roomPicker.newRoomPlaceholder');
  newRoomInput.style.display = hasExistingRooms ? 'none' : '';
  form.appendChild(newRoomInput);

  if (roomSelect) {
   roomSelect.addEventListener('change', () => {
     newRoomInput.style.display = roomSelect?.value === 'new' ? '' : 'none';
   });
  }

  const submit = document.createElement('button');
  submit.type = 'submit';
  submit.textContent = t('action.addPlant');
  form.appendChild(submit);

  form.addEventListener('submit', (event) => {
   event.preventDefault();
   if (!hasExistingRooms) {
     handlers.onRoomSubmit({ newRoomName: newRoomInput.value });
   } else if (roomSelect?.value === 'new') {
     handlers.onRoomSubmit({ newRoomName: newRoomInput.value });
   } else {
     handlers.onRoomSubmit({ roomId: Number(roomSelect?.value ?? 0) });
   }
  });

  return form;
}

function createQuickActionsIcon(): SVGSVGElement {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('width', '26');
  svg.setAttribute('height', '26');
  svg.setAttribute('fill', 'currentColor');
  svg.setAttribute('aria-hidden', 'true');

  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'M12 2 14 10 22 12 14 14 12 22 10 14 2 12 10 10Z');
  svg.appendChild(path);

  return svg;
}
