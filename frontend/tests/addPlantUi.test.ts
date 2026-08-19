import { describe, expect, it, vi, beforeEach } from 'vitest';
import {
  consumeInterruptedCapture,
  renderAddButton,
  renderAddPlantModal,
  renderNicknameEditorModal,
  renderTextPromptModal,
} from '../src/addPlantUi';
import type { AddPlantModalHandlers } from '../src/addPlantUi';

const PENDING_CAPTURE_KEY = 'droplet:pendingPhotoCapture';

function handlers(overrides: Partial<AddPlantModalHandlers> = {}): AddPlantModalHandlers {
  return {
    rooms: [{ id: 1, name: 'Kitchen', sort_order: 0, plant_count: 0, due_count: 0, overdue_count: 0 }],
    onFileSelected: vi.fn(),
    onAcceptCandidate: vi.fn(),
    onRejectAll: vi.fn(),
    onSearchByName: vi.fn().mockResolvedValue([]),
    onManualSubmit: vi.fn(),
    onSkipNickname: vi.fn(),
    onSetNickname: vi.fn(),
    onRoomSubmit: vi.fn(),
    onCancel: vi.fn(),
    ...overrides,
  };
}

describe('renderAddButton', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it('should_open_hidden_file_input_when_button_clicked', () => {
    const container = document.createElement('div');
    const choiceContainer = document.createElement('div');
    renderAddButton(container, choiceContainer, { onFileSelected: vi.fn(), onChooseRoom: vi.fn(), onChooseDiagnose: vi.fn() });
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;
    const clickSpy = vi.spyOn(input, 'click');

    container.querySelector<HTMLButtonElement>('.add-plant-button')?.click();
    choiceContainer.querySelector<HTMLButtonElement>('[data-add-choice-plant]')?.click();

    expect(clickSpy).toHaveBeenCalled();
  });

  it('should_call_onChooseRoom_when_room_is_selected_from_the_plus_menu', () => {
    const container = document.createElement('div');
    const choiceContainer = document.createElement('div');
    const onChooseRoom = vi.fn();

    renderAddButton(container, choiceContainer, { onFileSelected: vi.fn(), onChooseRoom, onChooseDiagnose: vi.fn() });

    container.querySelector<HTMLButtonElement>('.add-plant-button')?.click();
    choiceContainer.querySelector<HTMLButtonElement>('[data-add-choice-room]')?.click();

    expect(onChooseRoom).toHaveBeenCalledTimes(1);
  });

  it('should_call_onChooseDiagnose_when_diagnose_plant_issue_is_selected_from_the_quick_actions_menu', () => {
    // Moved here from the per-plant "⋮" menu (TODO.md) since asking for a
    // diagnosis shouldn't require first drilling into a specific plant tile.
    const container = document.createElement('div');
    const choiceContainer = document.createElement('div');
    const onChooseDiagnose = vi.fn();

    renderAddButton(container, choiceContainer, { onFileSelected: vi.fn(), onChooseRoom: vi.fn(), onChooseDiagnose });

    container.querySelector<HTMLButtonElement>('.add-plant-button')?.click();
    choiceContainer.querySelector<HTMLButtonElement>('[data-add-choice-diagnose]')?.click();

    expect(onChooseDiagnose).toHaveBeenCalledTimes(1);
  });

  it('should_call_onFileSelected_when_a_file_is_chosen', () => {
    const container = document.createElement('div');
    const choiceContainer = document.createElement('div');
    const onFileSelected = vi.fn();
    renderAddButton(container, choiceContainer, { onFileSelected, onChooseRoom: vi.fn(), onChooseDiagnose: vi.fn() });
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;
    const file = new File(['x'], 'plant.jpg', { type: 'image/jpeg' });
    Object.defineProperty(input, 'files', { value: [file] });

    container.querySelector<HTMLButtonElement>('.add-plant-button')?.click();
    choiceContainer.querySelector<HTMLButtonElement>('[data-add-choice-plant]')?.click();
    input.dispatchEvent(new Event('change'));

    expect(onFileSelected).toHaveBeenCalledWith(file);
  });

  it('should_call_onFileSelected_on_window_focus_when_change_event_never_fires', () => {
    // Regression test for TODO.md: on some Android browsers the camera app
    // hands the photo back (populating input.files) without the input's
    // 'change' event ever firing, so nothing happens until a second photo
    // is taken. Returning to the tab (window regains focus) must recover
    // that dropped file.
    const container = document.createElement('div');
    const choiceContainer = document.createElement('div');
    const onFileSelected = vi.fn();
    renderAddButton(container, choiceContainer, { onFileSelected, onChooseRoom: vi.fn(), onChooseDiagnose: vi.fn() });
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;
    const file = new File(['x'], 'plant.jpg', { type: 'image/jpeg' });
    Object.defineProperty(input, 'files', { value: [file] });

    // Note: no 'change' event dispatched here — simulating the dropped event.
    window.dispatchEvent(new Event('focus'));

    expect(onFileSelected).toHaveBeenCalledWith(file);
  });

  it('should_not_call_onFileSelected_again_on_a_later_window_focus_with_no_new_file', () => {
    const container = document.createElement('div');
    const choiceContainer = document.createElement('div');
    const onFileSelected = vi.fn();
    renderAddButton(container, choiceContainer, { onFileSelected, onChooseRoom: vi.fn(), onChooseDiagnose: vi.fn() });
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;
    const file = new File(['x'], 'plant.jpg', { type: 'image/jpeg' });
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    input.dispatchEvent(new Event('change'));
    expect(onFileSelected).toHaveBeenCalledTimes(1);

    // input.files is cleared after being handled, so an unrelated later
    // focus event (e.g. switching back from another app) must not re-fire.
    Object.defineProperty(input, 'files', { value: [], configurable: true });
    window.dispatchEvent(new Event('focus'));

    expect(onFileSelected).toHaveBeenCalledTimes(1);
  });

  it('should_flag_an_interrupted_capture_when_the_page_reloads_before_a_file_ever_arrives', () => {
    // Regression test for TODO.md: launching the native camera app can make
    // Android kill and reload our backgrounded tab to reclaim memory (the
    // "memory" notice the user saw), wiping all JS state before the photo
    // ever reaches us. Simulate that by clicking the button (which marks a
    // capture as started) and never delivering a file at all — as if this
    // page instance were about to be torn down.
    const container = document.createElement('div');
    const choiceContainer = document.createElement('div');
    renderAddButton(container, choiceContainer, { onFileSelected: vi.fn(), onChooseRoom: vi.fn(), onChooseDiagnose: vi.fn() });

    container.querySelector<HTMLButtonElement>('.add-plant-button')?.click();
    choiceContainer.querySelector<HTMLButtonElement>('[data-add-choice-plant]')?.click();

    // Simulate the reload: a fresh module-level check, as main.ts does at
    // startup, on the *next* page load — the marker survives in sessionStorage.
    expect(consumeInterruptedCapture()).toBe(true);
    // The marker is consumed (one-shot) so it doesn't fire again next reload.
    expect(consumeInterruptedCapture()).toBe(false);
  });

  it('should_not_flag_an_interrupted_capture_once_a_photo_is_successfully_delivered', () => {
    const container = document.createElement('div');
    const choiceContainer = document.createElement('div');
    renderAddButton(container, choiceContainer, { onFileSelected: vi.fn(), onChooseRoom: vi.fn(), onChooseDiagnose: vi.fn() });
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;
    const file = new File(['x'], 'plant.jpg', { type: 'image/jpeg' });

    container.querySelector<HTMLButtonElement>('.add-plant-button')?.click();
    choiceContainer.querySelector<HTMLButtonElement>('[data-add-choice-plant]')?.click();
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    input.dispatchEvent(new Event('change'));

    expect(consumeInterruptedCapture()).toBe(false);
  });

  it('should_not_flag_an_interrupted_capture_when_the_picker_is_simply_cancelled', () => {
    const container = document.createElement('div');
    const choiceContainer = document.createElement('div');
    renderAddButton(container, choiceContainer, { onFileSelected: vi.fn(), onChooseRoom: vi.fn(), onChooseDiagnose: vi.fn() });
    const input = container.querySelector<HTMLInputElement>('input[type="file"]')!;

    container.querySelector<HTMLButtonElement>('.add-plant-button')?.click();
    choiceContainer.querySelector<HTMLButtonElement>('[data-add-choice-plant]')?.click();
    // User backed out of the picker without choosing a file — this page
    // instance survives to see that (no reload), so it's not "interrupted".
    Object.defineProperty(input, 'files', { value: [], configurable: true });
    window.dispatchEvent(new Event('focus'));

    expect(consumeInterruptedCapture()).toBe(false);
  });
});

describe('renderAddPlantModal', () => {
  it('should_hide_container_on_idle_step', () => {
    const container = document.createElement('div');

    renderAddPlantModal(container, { name: 'idle' }, handlers());

    expect(container.classList.contains('hidden')).toBe(true);
    expect(container.children.length).toBe(0);
  });

  it('should_render_the_modal_close_button_as_an_icon_button', () => {
    const container = document.createElement('div');

    renderAddPlantModal(container, { name: 'identifying' }, handlers());

    const closeButton = container.querySelector<HTMLButtonElement>('.modal-close')!;
    expect(closeButton.textContent).toBe('×');
    expect(closeButton.getAttribute('aria-label')).toBe('Cancel');
  });

  it('should_show_a_room_creation_hint_when_no_rooms_exist', () => {
    const container = document.createElement('div');

    renderAddPlantModal(
      container,
      { name: 'room-picker', photoId: 'p.jpg', species_id: 1 },
      handlers({ rooms: [] }),
    );

    expect(container.textContent).toContain('You do not have any rooms yet');
    expect(container.querySelector('select')).toBeNull();
    expect(container.querySelector<HTMLInputElement>('.new-room-input')).not.toBeNull();
  });

  it('should_show_identifying_message', () => {
    const container = document.createElement('div');

    renderAddPlantModal(container, { name: 'identifying' }, handlers());

    expect(container.textContent).toContain('Identifying');
  });

  it('should_show_a_spinner_animation_while_identifying', () => {
    const container = document.createElement('div');

    renderAddPlantModal(container, { name: 'identifying' }, handlers());

    expect(container.querySelector('.spinner')).not.toBeNull();
  });

  it('should_render_top_candidate_with_yes_no_buttons', () => {
    const container = document.createElement('div');
    const onAcceptCandidate = vi.fn();

    renderAddPlantModal(
      container,
      {
        name: 'candidates',
        photoId: 'p.jpg',
        candidates: [
          {
            species_id: 1,
            scientific_name: 'Monstera deliciosa',
            common_name: 'Swiss cheese plant',
            confidence: 0.9,
            reference_image_url: 'https://example.com/m.jpg',
          },
        ],
      },
      handlers({ onAcceptCandidate }),
    );

    expect(container.textContent).toContain('Is this a Swiss cheese plant?');
    container.querySelector<HTMLButtonElement>('.candidate-yes')?.click();
    expect(onAcceptCandidate).toHaveBeenCalledWith(expect.objectContaining({ scientific_name: 'Monstera deliciosa' }));
  });

  it('should_call_onRejectAll_when_no_clicked', () => {
    const container = document.createElement('div');
    const onRejectAll = vi.fn();

    renderAddPlantModal(
      container,
      {
        name: 'candidates',
        photoId: 'p.jpg',
        candidates: [
          { species_id: 1, scientific_name: 'X', common_name: null, confidence: 0.5, reference_image_url: null },
        ],
      },
      handlers({ onRejectAll }),
    );

    container.querySelector<HTMLButtonElement>('.candidate-no')?.click();

    expect(onRejectAll).toHaveBeenCalled();
  });

  it('should_list_other_candidates_and_accept_on_click', () => {
    const container = document.createElement('div');
    const onAcceptCandidate = vi.fn();

    renderAddPlantModal(
      container,
      {
        name: 'candidates',
        photoId: 'p.jpg',
        candidates: [
          { species_id: 1, scientific_name: 'A', common_name: null, confidence: 0.9, reference_image_url: null },
          { species_id: 2, scientific_name: 'B', common_name: null, confidence: 0.1, reference_image_url: null },
        ],
      },
      handlers({ onAcceptCandidate }),
    );

    const otherButtons = container.querySelectorAll<HTMLButtonElement>('.other-candidates button');
    expect(otherButtons.length).toBe(1);
    otherButtons[0].click();
    expect(onAcceptCandidate).toHaveBeenCalledWith(expect.objectContaining({ scientific_name: 'B' }));
  });

  it('should_render_reference_image_for_other_candidates_when_available', () => {
    const container = document.createElement('div');

    renderAddPlantModal(
      container,
      {
        name: 'candidates',
        photoId: 'p.jpg',
        candidates: [
          { species_id: 1, scientific_name: 'A', common_name: null, confidence: 0.9, reference_image_url: null },
          {
            species_id: 2,
            scientific_name: 'B',
            common_name: null,
            confidence: 0.1,
            reference_image_url: 'https://example.com/b.jpg',
          },
          { species_id: 3, scientific_name: 'C', common_name: null, confidence: 0.05, reference_image_url: null },
        ],
      },
      handlers(),
    );

    const thumbs = container.querySelectorAll<HTMLImageElement>('.other-candidates img.other-candidate-thumb');
    expect(thumbs.length).toBe(1);
    expect(thumbs[0].src).toBe('https://example.com/b.jpg');
    expect(thumbs[0].alt).toBe('B');

    const otherButtons = container.querySelectorAll<HTMLButtonElement>('.other-candidates button');
    expect(otherButtons.length).toBe(2);
    expect(otherButtons[0].querySelector('img')).not.toBeNull();
    expect(otherButtons[1].querySelector('img')).toBeNull();
  });

  it('should_submit_manual_form_with_name_and_days', () => {
    const container = document.createElement('div');
    const onManualSubmit = vi.fn();

    renderAddPlantModal(container, { name: 'manual', photoId: 'p.jpg' }, handlers({ onManualSubmit }));

    const nameInput = container.querySelector<HTMLInputElement>('.manual-name-input')!;
    nameInput.value = 'My weird cactus';
    container.querySelector('form')?.dispatchEvent(new Event('submit', { cancelable: true }));

    expect(onManualSubmit).toHaveBeenCalledWith('My weird cactus', 7);
  });

  it('should_apply_interval_shortcut_chip_to_days_input', () => {
    const container = document.createElement('div');
    const onManualSubmit = vi.fn();

    renderAddPlantModal(container, { name: 'manual', photoId: 'p.jpg' }, handlers({ onManualSubmit }));

    const chips = container.querySelectorAll<HTMLButtonElement>('.interval-shortcuts button');
    chips[2].click(); // "every 2 weeks" -> 14
    container.querySelector('form')?.dispatchEvent(new Event('submit', { cancelable: true }));

    expect(onManualSubmit).toHaveBeenCalledWith('', 14);
  });

  it('should_search_by_name_and_render_selectable_results', async () => {
    const container = document.createElement('div');
    const onSearchByName = vi.fn().mockResolvedValue([
      { species_id: 7, scientific_name: 'Monstera deliciosa', common_name: 'Swiss cheese plant', confidence: null, reference_image_url: null },
    ]);
    const onAcceptCandidate = vi.fn();

    renderAddPlantModal(container, { name: 'manual', photoId: 'p.jpg' }, handlers({ onSearchByName, onAcceptCandidate }));

    const nameInput = container.querySelector<HTMLInputElement>('.manual-name-input')!;
    nameInput.value = 'monstera';
    container.querySelector<HTMLButtonElement>('.manual-search-button')?.click();
    expect(onSearchByName).toHaveBeenCalledWith('monstera');

    await Promise.resolve();
    await Promise.resolve();

    const resultButton = container.querySelector<HTMLButtonElement>('.search-result-button')!;
    expect(resultButton.textContent).toBe('Swiss cheese plant');
    resultButton.click();
    expect(onAcceptCandidate).toHaveBeenCalledWith(expect.objectContaining({ species_id: 7 }));
  });

  it('should_show_loading_indicator_while_search_is_in_flight', async () => {
    const container = document.createElement('div');
    let resolveSearch!: (results: never[]) => void;
    const onSearchByName = vi.fn(() => new Promise<never[]>((resolve) => { resolveSearch = resolve; }));

    renderAddPlantModal(container, { name: 'manual', photoId: 'p.jpg' }, handlers({ onSearchByName }));

    const nameInput = container.querySelector<HTMLInputElement>('.manual-name-input')!;
    nameInput.value = 'monstera';
    const searchButton = container.querySelector<HTMLButtonElement>('.manual-search-button')!;
    searchButton.click();

    expect(container.querySelector('.search-loading')).not.toBeNull();
    expect(searchButton.disabled).toBe(true);

    resolveSearch([]);
    await Promise.resolve();
    await Promise.resolve();

    expect(container.querySelector('.search-loading')).toBeNull();
    expect(searchButton.disabled).toBe(false);
  });

  it('should_show_no_matches_message_when_search_returns_nothing', async () => {
    const container = document.createElement('div');
    const onSearchByName = vi.fn().mockResolvedValue([]);

    renderAddPlantModal(container, { name: 'manual', photoId: 'p.jpg' }, handlers({ onSearchByName }));

    const nameInput = container.querySelector<HTMLInputElement>('.manual-name-input')!;
    nameInput.value = 'unknown plant';
    container.querySelector<HTMLButtonElement>('.manual-search-button')?.click();

    await Promise.resolve();
    await Promise.resolve();

    expect(container.querySelector('.search-no-results')?.textContent).toContain('No matches found');
  });

  it('should_not_search_when_name_input_is_blank', () => {
    const container = document.createElement('div');
    const onSearchByName = vi.fn();

    renderAddPlantModal(container, { name: 'manual', photoId: 'p.jpg' }, handlers({ onSearchByName }));

    container.querySelector<HTMLButtonElement>('.manual-search-button')?.click();

    expect(onSearchByName).not.toHaveBeenCalled();
  });

  it('should_submit_room_picker_with_existing_room', () => {
    const container = document.createElement('div');
    const onRoomSubmit = vi.fn();

    renderAddPlantModal(
      container,
      { name: 'room-picker', photoId: 'p.jpg', species_id: 5, nickname: 'Monty' },
      handlers({ onRoomSubmit }),
    );

    container.querySelector('form')?.dispatchEvent(new Event('submit', { cancelable: true }));

    expect(onRoomSubmit).toHaveBeenCalledWith({ roomId: 1 });
  });

  it('should_place_the_new_room_input_after_the_existing_room_list', () => {
    const container = document.createElement('div');

    renderAddPlantModal(
      container,
      { name: 'room-picker', photoId: 'p.jpg', species_id: 5, nickname: 'Monty' },
      handlers(),
    );

    const form = container.querySelector<HTMLFormElement>('.room-picker-form')!;
    const order = Array.from(form.children).map((el) => el.className || el.tagName.toLowerCase());
    expect(order.indexOf('room-select')).toBeLessThan(order.indexOf('new-room-input'));
  });

  it('should_submit_room_picker_with_new_room_name', () => {
    const container = document.createElement('div');
    const onRoomSubmit = vi.fn();

    renderAddPlantModal(
      container,
      { name: 'room-picker', photoId: 'p.jpg', species_id: 5, nickname: 'Monty' },
      handlers({ onRoomSubmit }),
    );

    const select = container.querySelector<HTMLSelectElement>('.room-select')!;
    select.value = 'new';
    container.querySelector<HTMLInputElement>('.new-room-input')!.value = 'Attic';
    container.querySelector('form')?.dispatchEvent(new Event('submit', { cancelable: true }));

    expect(onRoomSubmit).toHaveBeenCalledWith({ newRoomName: 'Attic' });
  });

  it('should_render_nickname_editor_modal_with_a_prefilled_value', () => {
    const container = document.createElement('div');
    const onSubmit = vi.fn();

    renderNicknameEditorModal(container, {
      title: 'Update nickname',
      currentNickname: 'Fern',
      onSubmit,
      onCancel: vi.fn(),
    });

    expect(container.textContent).toContain('Update nickname');
    expect(container.querySelector<HTMLInputElement>('.nickname-editor-input')?.value).toBe('Fern');

    container.querySelector('form')?.dispatchEvent(new Event('submit', { cancelable: true }));
    expect(onSubmit).toHaveBeenCalledWith('Fern');
  });

  it('should_render_a_generic_text_prompt_modal', () => {
    const container = document.createElement('div');
    const onSubmit = vi.fn();

    renderTextPromptModal(container, {
      title: 'Rename room',
      currentValue: 'Kitchen',
      placeholder: 'Room name',
      submitLabel: 'Save',
      onSubmit,
      onCancel: vi.fn(),
    });

    expect(container.textContent).toContain('Rename room');
    expect(container.querySelector<HTMLInputElement>('input')?.value).toBe('Kitchen');

    container.querySelector('form')?.dispatchEvent(new Event('submit', { cancelable: true }));
    expect(onSubmit).toHaveBeenCalledWith('Kitchen');
  });

  it('should_allow_hiding_the_bottom_cancel_button', () => {
    const container = document.createElement('div');

    renderTextPromptModal(container, {
      title: 'Rename room',
      currentValue: 'Kitchen',
      placeholder: 'Room name',
      submitLabel: 'Save',
      showCancelButton: false,
      onSubmit: vi.fn(),
      onCancel: vi.fn(),
    });

    expect(container.querySelector('.text-prompt-cancel')).toBeNull();
  });

  it('should_show_nickname_prompt_question', () => {
    const container = document.createElement('div');

    renderAddPlantModal(
      container,
      { name: 'nickname-prompt', photoId: 'p.jpg', species_id: 5, defaultName: 'Swiss cheese plant' },
      handlers(),
    );

    expect(container.textContent).toContain('Want to give this Swiss cheese plant a nickname?');
  });

  it('should_call_onSkipNickname_when_no_clicked', () => {
    const container = document.createElement('div');
    const onSkipNickname = vi.fn();

    renderAddPlantModal(
      container,
      { name: 'nickname-prompt', photoId: 'p.jpg', species_id: 5, defaultName: 'Swiss cheese plant' },
      handlers({ onSkipNickname }),
    );

    container.querySelector<HTMLButtonElement>('.nickname-no')?.click();

    expect(onSkipNickname).toHaveBeenCalled();
  });

  it('should_reveal_nickname_input_only_after_yes_clicked', () => {
    const container = document.createElement('div');

    renderAddPlantModal(
      container,
      { name: 'nickname-prompt', photoId: 'p.jpg', species_id: 5, defaultName: 'Swiss cheese plant' },
      handlers(),
    );

    const nicknameInput = container.querySelector<HTMLInputElement>('.nickname-input')!;
    expect(nicknameInput.style.display).toBe('none');

    container.querySelector<HTMLButtonElement>('.nickname-yes')?.click();

    expect(nicknameInput.style.display).not.toBe('none');
  });

  it('should_call_onSetNickname_with_typed_value_on_submit', () => {
    const container = document.createElement('div');
    const onSetNickname = vi.fn();

    renderAddPlantModal(
      container,
      { name: 'nickname-prompt', photoId: 'p.jpg', species_id: 5, defaultName: 'Swiss cheese plant' },
      handlers({ onSetNickname }),
    );

    container.querySelector<HTMLButtonElement>('.nickname-yes')?.click();
    container.querySelector<HTMLInputElement>('.nickname-input')!.value = 'Monty';
    container.querySelector('form')?.dispatchEvent(new Event('submit', { cancelable: true }));

    expect(onSetNickname).toHaveBeenCalledWith('Monty');
  });

  it('should_show_error_message', () => {
    const container = document.createElement('div');

    renderAddPlantModal(container, { name: 'error', message: 'Something broke' }, handlers());

    expect(container.textContent).toContain('Something broke');
  });

  it('should_call_onCancel_when_close_button_clicked', () => {
    const container = document.createElement('div');
    const onCancel = vi.fn();

    renderAddPlantModal(container, { name: 'identifying' }, handlers({ onCancel }));
    container.querySelector<HTMLButtonElement>('.modal-close')?.click();

    expect(onCancel).toHaveBeenCalled();
  });
});
