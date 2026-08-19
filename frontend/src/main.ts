import './style.css';
import {
  createManualSpecies,
  createPlant,
  createRoom,
  deletePlant,
  deleteRoom,
  diagnosePlant,
  fetchPlants,
  fetchRooms,
  identifyPhoto,
  lookupSpecies,
  renameRoom,
  resetPlantInterval,
  undoWatering,
  updatePlantInterval,
  updatePlantNickname,
  updatePlantPhoto,
  updatePlantRoom,
  waterPlant,
  waterRoom,
  type PlantOut,
  type RoomSummary,
} from './api';
import { AddPlantFlow } from './addPlantFlow';
import {
  consumeInterruptedCapture,
  renderAddButton,
  renderAddPlantModal,
  renderNicknameEditorModal,
  renderTextPromptModal,
} from './addPlantUi';
import { renderDiagnoseModal, renderDiagnosePlantPickerModal, createDiagnoseCaptureInput, type DiagnoseStep } from './diagnosePlantUi';
import { renderMoveRoomModal } from './moveRoomUi';
import { renderApp } from './render';
import { showToast, showUndoToast } from './toast';
import { locale, t } from './i18n';
import { acquireWakeLock, releaseWakeLock } from './wakeLock';

document.documentElement.lang = locale;


const appRoot = document.querySelector<HTMLDivElement>('#app')!;
const toastRoot = document.querySelector<HTMLDivElement>('#toast-root')!;
const addButtonRoot = document.querySelector<HTMLDivElement>('#add-button-root')!;
const addChoiceModalRoot = document.querySelector<HTMLDivElement>('#add-choice-modal-root')!;
const addModalRoot = document.querySelector<HTMLDivElement>('#add-modal-root')!;
const nicknameModalRoot = document.querySelector<HTMLDivElement>('#nickname-modal-root')!;
const roomRenameModalRoot = document.querySelector<HTMLDivElement>('#room-rename-modal-root')!;
const moveRoomModalRoot = document.querySelector<HTMLDivElement>('#move-room-modal-root')!;
const diagnosePickerModalRoot = document.querySelector<HTMLDivElement>('#diagnose-picker-modal-root')!;
const diagnoseModalRoot = document.querySelector<HTMLDivElement>('#diagnose-modal-root')!;

let currentRooms: RoomSummary[] = [];
let currentPlants: PlantOut[] = [];
let expandedPlantId: number | null = null;
let expandedRoomId: number | null = null;
let moveRoomPlantId: number | null = null;
let editingNicknamePlantId: number | null = null;
let editingRoomId: number | null = null;
let diagnosePlantId: number | null = null;
let diagnoseStep: DiagnoseStep = { name: 'idle' };
let diagnosePickerOpen = false;

function renderCurrentView(): void {
  renderApp(appRoot, {
    rooms: currentRooms,
    plants: currentPlants,
    now: new Date(),
    onWaterPlant: handleWaterPlant,
    onWaterRoom: handleWaterRoom,
    expandedPlantId,
    onToggleDetail: handleToggleDetail,
    onSetIntervalDays: handleSetIntervalDays,
    onResetInterval: handleResetInterval,
    onRemovePlant: handleRemovePlant,
    onRemoveRoom: handleRemoveRoom,
    onChangePhoto: handleChangePhoto,
    onRenameNickname: handleRenameNickname,
    onOpenMoveRoom: handleOpenMoveRoom,
    expandedRoomId,
    onToggleRoomDetail: handleToggleRoomDetail,
    onRenameRoom: handleRenameRoom,
  });
  // Hide the FAB button when any detail menu is expanded to avoid blocking clicks
  if (expandedPlantId !== null || expandedRoomId !== null) {
    document.body.classList.add('detail-expanded');
  } else {
    document.body.classList.remove('detail-expanded');
  }
}

async function refresh(): Promise<void> {
  const [rooms, plants] = await Promise.all([fetchRooms(), fetchPlants()]);
  currentRooms = rooms;
  currentPlants = plants;
  renderCurrentView();
  updateMoveRoomModal();
  updateNicknameModal();
  updateRoomRenameModal();
  updateDiagnosePickerModal();
  updateDiagnoseModal();
}

/**
 * Keeps the "move to room" popup (moveRoomUi.ts) in sync with whichever
 * plant is currently open, re-rendering it any time that plant or the room
 * list changes (e.g. after refresh()).
 */
function updateMoveRoomModal(): void {
  const plant = moveRoomPlantId === null ? null : (currentPlants.find((p) => p.id === moveRoomPlantId) ?? null);
  renderMoveRoomModal(moveRoomModalRoot, {
    plant,
    rooms: currentRooms,
    onSelectRoom: (roomId) => {
      if (moveRoomPlantId !== null) void handleMoveToRoom(moveRoomPlantId, roomId);
    },
    onCancel: handleCloseMoveRoom,
  });
}

function updateRoomRenameModal(): void {
  const room = editingRoomId === null ? null : (currentRooms.find((r) => r.id === editingRoomId) ?? null);
  if (!room) {
    roomRenameModalRoot.replaceChildren();
    roomRenameModalRoot.classList.add('hidden');
    return;
  }

  renderTextPromptModal(roomRenameModalRoot, {
    title: t('room.renamePrompt'),
    currentValue: room.name,
    placeholder: t('room.renamePrompt'),
    submitLabel: t('room.renameSubmit'),
    onSubmit: (name) => {
      if (editingRoomId !== null) void handleUpdateRoomName(editingRoomId, name);
    },
    onCancel: handleCloseRoomRenameModal,
    valueClassName: 'room-rename-input',
    submitClassName: 'room-rename-submit',
    showCancelButton: false,
  });
}

function handleOpenMoveRoom(plantId: number): void {
  moveRoomPlantId = plantId;
  updateMoveRoomModal();
}

function handleCloseMoveRoom(): void {
  moveRoomPlantId = null;
  updateMoveRoomModal();
}

function updateNicknameModal(): void {
  const plant = editingNicknamePlantId === null ? null : (currentPlants.find((p) => p.id === editingNicknamePlantId) ?? null);
  if (!plant) {
    nicknameModalRoot.replaceChildren();
    nicknameModalRoot.classList.add('hidden');
    return;
  }

  renderNicknameEditorModal(nicknameModalRoot, {
    title: t('nickname.renamePrompt'),
    currentNickname: plant.nickname_is_custom ? plant.nickname : '',
    onSubmit: (nickname) => {
      if (editingNicknamePlantId !== null) void handleUpdateNickname(editingNicknamePlantId, nickname);
    },
    onCancel: handleCloseNicknameModal,
  });
}

function handleOpenNicknameModal(plantId: number): void {
  editingNicknamePlantId = plantId;
  updateNicknameModal();
}

function handleCloseNicknameModal(): void {
  editingNicknamePlantId = null;
  updateNicknameModal();
}

function handleOpenRoomRenameModal(roomId: number): void {
  editingRoomId = roomId;
  updateRoomRenameModal();
}

function handleCloseRoomRenameModal(): void {
  editingRoomId = null;
  updateRoomRenameModal();
}

function updateDiagnoseModal(): void {
  const plant = diagnosePlantId === null ? null : (currentPlants.find((p) => p.id === diagnosePlantId) ?? null);
  if (!plant) {
    diagnoseModalRoot.replaceChildren();
    diagnoseModalRoot.classList.add('hidden');
    return;
  }

  renderDiagnoseModal(diagnoseModalRoot, {
    step: diagnoseStep,
    plantName: plant.nickname,
    onDismiss: handleDismissDiagnose,
  });
}

function handleDismissDiagnose(): void {
  diagnosePlantId = null;
  diagnoseStep = { name: 'idle' };
  updateDiagnoseModal();
}

/**
 * "Which plant is this for?" step (TODO.md: "Recognize issues with the
 * plants... provide suggestions for how to fix them") shown after picking
 * "Diagnose plant issue" from the bottom-right quick-actions chooser — see
 * diagnosePlantUi.ts's doc comment for why this replaced the old per-plant
 * "⋮" menu entry point.
 */
function updateDiagnosePickerModal(): void {
  renderDiagnosePlantPickerModal(diagnosePickerModalRoot, {
    open: diagnosePickerOpen,
    plants: currentPlants,
    onSelectPlant: handleSelectPlantForDiagnose,
    onCancel: handleCancelDiagnosePicker,
  });
}

function handleOpenDiagnosePicker(): void {
  diagnosePickerOpen = true;
  updateDiagnosePickerModal();
}

function handleCancelDiagnosePicker(): void {
  diagnosePickerOpen = false;
  updateDiagnosePickerModal();
}

function handleSelectPlantForDiagnose(plantId: number): void {
  diagnosePickerOpen = false;
  updateDiagnosePickerModal();
  pendingDiagnosePlantId = plantId;
  diagnoseCaptureInput.click();
}

/**
 * "Diagnose plant issue" (TODO.md: "Recognize issues with the plants, such as
 * yellowing leaves, pests, etc., and provide suggestions for how to fix
 * them"), triggered once a plant has been picked (handleSelectPlantForDiagnose
 * above) and a fresh photo captured via diagnoseCaptureInput — this just
 * drives the loading/result/error states of the diagnose modal.
 */
async function handleDiagnosePlant(plantId: number, file: File): Promise<void> {
  diagnosePlantId = plantId;
  diagnoseStep = { name: 'loading' };
  updateDiagnoseModal();

  try {
    const result = await diagnosePlant(plantId, file);
    diagnoseStep = { name: 'result', result };
  } catch (err) {
    console.error('Failed to diagnose plant', err);
    const unavailable = err instanceof Error && err.message.includes('503');
    diagnoseStep = { name: 'error', message: unavailable ? t('error.diagnoseUnavailable') : t('error.diagnose') };
  }

  updateDiagnoseModal();
}

// Holds the plant picked in the diagnose flow's plant-picker step until the
// photo capture triggered below hands a file back; see handleSelectPlantForDiagnose.
let pendingDiagnosePlantId: number | null = null;

const diagnoseCaptureInput = createDiagnoseCaptureInput((file) => {
  if (pendingDiagnosePlantId === null) return;
  const plantId = pendingDiagnosePlantId;
  pendingDiagnosePlantId = null;
  void handleDiagnosePlant(plantId, file);
});
document.body.appendChild(diagnoseCaptureInput);


async function handleWaterPlant(plantId: number): Promise<void> {
  const result = await waterPlant(plantId);
  await refresh();
  showUndoToast(toastRoot, t('toast.watered'), () => handleUndo(result.undo_token));
}

async function handleWaterRoom(roomId: number): Promise<void> {
  const result = await waterRoom(roomId);
  await refresh();
  showUndoToast(toastRoot, t('toast.wateredPlants', { count: result.plant_ids.length }), () =>
    handleUndo(result.undo_token),
  );
}

async function handleUndo(token: string): Promise<void> {
  await undoWatering(token);
  await refresh();
}

function handleToggleDetail(plantId: number): void {
  expandedPlantId = expandedPlantId === plantId ? null : plantId;
  renderCurrentView();
}

/**
 * Setting the cadence stepper changes the plant's next-due date under the
 * hood, but that's easy to miss since the stepper row itself already shows
 * the new day count — so we surface a toast (TODO.md) as the same kind of
 * confirmation used for the other "did this actually happen?" actions above.
 */
async function handleSetIntervalDays(plantId: number, days: number): Promise<void> {
  await updatePlantInterval(plantId, days);
  await refresh();
  showToast(toastRoot, t('toast.intervalUpdated', { days }));
}

async function handleResetInterval(plantId: number): Promise<void> {
  await resetPlantInterval(plantId);
  await refresh();
  showToast(toastRoot, t('toast.intervalReset'));
}

async function handleChangePhoto(plantId: number, file: File): Promise<void> {
  try {
    await updatePlantPhoto(plantId, file);
  } catch (err) {
    console.error('Failed to update plant photo', err);
    window.alert(t('error.changePhoto'));
    return;
  }

  await refresh();
  showToast(toastRoot, t('toast.photoChanged'));
}

/**
 * "Rename plant/nickname" (TODO.md), tucked behind the "⋮" detail menu
 * (render.ts's "Add nickname"/"Update nickname" button) — a simple native
 * prompt, same lightweight pattern as the window.confirm used for removal
 * below, rather than a bespoke inline form for something done rarely.
 */
function handleRenameNickname(plantId: number): void {
  handleOpenNicknameModal(plantId);
}

async function handleUpdateNickname(plantId: number, nickname: string): Promise<void> {
  try {
    await updatePlantNickname(plantId, nickname);
  } catch (err) {
    console.error('Failed to update nickname', err);
    window.alert(t('error.updateNickname'));
    return;
  }

  editingNicknamePlantId = null;
  updateNicknameModal();
  await refresh();
  showToast(toastRoot, t('toast.nicknameUpdated'));
}

/**
 * "Move plant to different room" (TODO.md), triggered from the popup opened
 * by render.ts's "Move to room" button (moveRoomUi.ts) — same lightweight
 * pattern as the other rarely-used actions above, since moving a plant
 * between rooms isn't something done frequently.
 */
async function handleMoveToRoom(plantId: number, roomId: number): Promise<void> {
  const room = currentRooms.find((r) => r.id === roomId);

  try {
    await updatePlantRoom(plantId, roomId);
  } catch (err) {
    console.error('Failed to move plant to room', err);
    window.alert(t('error.moveToRoom'));
    return;
  }

  moveRoomPlantId = null;
  await refresh();
  showToast(toastRoot, t('toast.plantMoved', { room: room?.name ?? '' }));
}

async function handleRemovePlant(plantId: number): Promise<void> {
  const plant = currentPlants.find((p) => p.id === plantId);
  const name = plant?.nickname ?? '';
  if (!window.confirm(t('confirm.removePlant', { name }))) return;

  try {
    await deletePlant(plantId);
  } catch (err) {
    console.error('Failed to remove plant', err);
    window.alert(t('error.removePlant'));
    return;
  }

  if (expandedPlantId === plantId) expandedPlantId = null;
  if (moveRoomPlantId === plantId) moveRoomPlantId = null;
  await refresh();
  showToast(toastRoot, t('toast.plantRemoved', { name }));
}

async function handleRemoveRoom(roomId: number): Promise<void> {
  const room = currentRooms.find((r) => r.id === roomId);
  const name = room?.name ?? '';
  if (!window.confirm(t('confirm.removeRoom', { name }))) return;

  try {
    await deleteRoom(roomId);
  } catch (err) {
    console.error('Failed to remove room', err);
    window.alert(t('error.removeRoom'));
    return;
  }

  await refresh();
  showToast(toastRoot, t('toast.roomRemoved', { name }));
}

function handleToggleRoomDetail(roomId: number): void {
  expandedRoomId = expandedRoomId === roomId ? null : roomId;
  renderCurrentView();
}

/**
 * "Rename room" (TODO.md), tucked behind the room header's "⋮" menu — same
 * modal pattern as the nickname editor, so it stays consistent with the rest
 * of the app.
 */
function handleRenameRoom(roomId: number): void {
  handleOpenRoomRenameModal(roomId);
}

async function handleUpdateRoomName(roomId: number, name: string): Promise<void> {
  const room = currentRooms.find((r) => r.id === roomId);
  if (!room || name === room.name) {
    handleCloseRoomRenameModal();
    return;
  }

  try {
    await renameRoom(roomId, name);
  } catch (err) {
    console.error('Failed to rename room', err);
    window.alert(t('error.renameRoom'));
    return;
  }

  editingRoomId = null;
  updateRoomRenameModal();
  await refresh();
  showToast(toastRoot, t('toast.roomRenamed', { name }));
}

async function handleAddRoom(): Promise<void> {
  const input = window.prompt(t('room.addPrompt'));
  if (input === null) return;
  const name = input.trim();
  if (!name) return;

  try {
    await createRoom(name);
  } catch (err) {
    console.error('Failed to create room', err);
    window.alert(t('error.createRoom'));
    return;
  }

  await refresh();
  showToast(toastRoot, t('toast.roomCreated', { name }));
}

const addPlantFlow = new AddPlantFlow(
  { identifyPhoto, lookupSpecies, createManualSpecies, createPlant, createRoom },
  (step) => {
    // Keep the screen awake for as long as the identifying animation is
    // shown — identification can take a few seconds and we don't want the
    // phone to lock mid-flow.
    if (step.name === 'identifying') {
      void acquireWakeLock();
    } else {
      void releaseWakeLock();
    }
    renderAddPlantModal(addModalRoot, step, {
      rooms: currentRooms,
      onFileSelected: (file) => addPlantFlow.submitPhoto(file),
      onAcceptCandidate: (candidate) => addPlantFlow.chooseCandidate(candidate),
      onRejectAll: () => addPlantFlow.rejectAllCandidates(),
      onSearchByName: (query) => addPlantFlow.searchByName(query),
      onManualSubmit: (name, days) => addPlantFlow.submitManual(name, days),
      onSkipNickname: () => addPlantFlow.skipNickname(),
      onSetNickname: (nickname) => addPlantFlow.setNickname(nickname),
      onRoomSubmit: (choice) => addPlantFlow.submitRoomAndCreate(choice),
      onCancel: () => addPlantFlow.cancel(),
    });
  },
  () => {
    refresh().catch((err) => console.error('Failed to refresh after adding plant', err));
  },
);

renderAddButton(addButtonRoot, addChoiceModalRoot, {
  onFileSelected: (file) => addPlantFlow.submitPhoto(file),
  onChooseRoom: handleAddRoom,
  onChooseDiagnose: handleOpenDiagnosePicker,
});

// Fix for TODO.md: tell the user plainly when the previous camera capture
// was silently lost to an Android memory-pressure tab reload (see
// addPlantUi.consumeInterruptedCapture), instead of leaving them wondering
// why nothing happened.
if (consumeInterruptedCapture()) {
  showToast(toastRoot, t('error.captureInterrupted'));
}

refresh().catch((err) => {
  console.error('Failed to load plants', err);
  appRoot.textContent = t('error.loadPlants');
});
