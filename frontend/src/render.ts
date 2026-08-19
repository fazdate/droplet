import type { PlantOut, RoomSummary } from './api';
import { renderCadenceEditor } from './cadenceEditor';
import { renderCareInfo } from './careInfo';
import { dueLabel } from './format';
import { t } from './i18n';

export function sortRoomsByUrgency(rooms: RoomSummary[]): RoomSummary[] {
  return [...rooms].sort((a, b) => b.overdue_count - a.overdue_count || a.sort_order - b.sort_order);
}

export function sortPlantsByUrgency(plants: PlantOut[]): PlantOut[] {
  return [...plants].sort((a, b) => {
    if (a.is_overdue !== b.is_overdue) {
      return a.is_overdue ? -1 : 1;
    }
    const aDue = a.next_due_at ? new Date(a.next_due_at).getTime() : Infinity;
    const bDue = b.next_due_at ? new Date(b.next_due_at).getTime() : Infinity;
    return aDue - bDue;
  });
}

export interface RenderAppOptions {
  rooms: RoomSummary[];
  plants: PlantOut[];
  now: Date;
  onWaterPlant: (plantId: number) => void;
  onWaterRoom: (roomId: number) => void;
  expandedPlantId: number | null;
  onToggleDetail: (plantId: number) => void;
  onSetIntervalDays: (plantId: number, days: number) => void;
  onResetInterval: (plantId: number) => void;
  onRemovePlant: (plantId: number) => void;
  onRemoveRoom: (roomId: number) => void;
  onChangePhoto: (plantId: number, file: File) => void;
  onRenameNickname: (plantId: number) => void;
  onOpenMoveRoom: (plantId: number) => void;
  expandedRoomId: number | null;
  onToggleRoomDetail: (roomId: number) => void;
  onRenameRoom: (roomId: number) => void;
}

export function renderApp(container: HTMLElement, options: RenderAppOptions): void {
  const { rooms, plants, now, onWaterPlant, onWaterRoom } = options;
  container.replaceChildren();

  const attentionCount = rooms.reduce((sum, room) => sum + room.due_count + room.overdue_count, 0);
  const attentionLabel =
    attentionCount === 1 ? t('summary.attentionOne') : t('summary.attentionMany', { count: attentionCount });

  const header = document.createElement('header');
  header.className = 'page-header';

  const summary = document.createElement('div');
  summary.className = 'page-summary';

  const summaryLabel = document.createElement('p');
  summaryLabel.className = 'page-summary-label';
  summaryLabel.textContent = attentionLabel;
  summary.appendChild(summaryLabel);

  header.appendChild(summary);

  container.appendChild(header);

  if (rooms.length === 0 && plants.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'empty-state';
    empty.appendChild(createEmptyStateIcon());
    const message = document.createElement('p');
    message.textContent = t('empty.noPlants');
    empty.appendChild(message);
    container.appendChild(empty);
    return;
  }

  const plantsByRoom = new Map<number, PlantOut[]>();
  for (const plant of plants) {
    const list = plantsByRoom.get(plant.room_id) ?? [];
    list.push(plant);
    plantsByRoom.set(plant.room_id, list);
  }

  for (const room of sortRoomsByUrgency(rooms)) {
    const section = document.createElement('section');
    section.className = 'room';

    const header = document.createElement('div');
    header.className = 'room-header';
    const title = document.createElement('span');
    title.className = 'room-title';
    title.textContent =
      room.overdue_count > 0
        ? `${room.name} — ${t('room.needWater', { count: room.overdue_count })}`
        : room.name;
    header.appendChild(title);

    if (room.plant_count > 0) {
      const waterAllButton = document.createElement('button');
      waterAllButton.textContent = t('action.waterAll');
      waterAllButton.dataset.waterRoom = String(room.id);
      waterAllButton.addEventListener('click', () => onWaterRoom(room.id));
      header.appendChild(waterAllButton);
    }

    if (room.plant_count === 0) {
      const removeRoomButton = document.createElement('button');
      removeRoomButton.className = 'remove-room-button';
      removeRoomButton.textContent = t('action.removeRoom');
      removeRoomButton.dataset.removeRoom = String(room.id);
      removeRoomButton.addEventListener('click', () => options.onRemoveRoom(room.id));
      header.appendChild(removeRoomButton);
    }

    const roomDetailToggle = document.createElement('button');
    roomDetailToggle.className = 'detail-toggle';
    roomDetailToggle.textContent = '⋮';
    roomDetailToggle.setAttribute('aria-label', t('action.moreOptions'));
    roomDetailToggle.dataset.detailRoom = String(room.id);
    roomDetailToggle.addEventListener('click', () => options.onToggleRoomDetail(room.id));
    header.appendChild(roomDetailToggle);

    section.appendChild(header);

    if (options.expandedRoomId === room.id) {
      section.appendChild(renderRoomDetail(room.id, options));
    }

    const roomPlants = sortPlantsByUrgency(plantsByRoom.get(room.id) ?? []);
    for (const plant of roomPlants) {
      section.appendChild(renderPlantTile(plant, now, onWaterPlant, options));
    }

    container.appendChild(section);
  }
}

/**
 * "Rename room" (TODO.md), tucked behind the room header's "⋮" menu — same
 * rationale as the plant-level "⋮" menu (see renderRenameNicknameControl
 * below): renaming a room isn't something done frequently, so it shouldn't
 * clutter the header next to "Water all"/"Remove room".
 */
function renderRoomDetail(roomId: number, options: RenderAppOptions): HTMLElement {
  const detail = document.createElement('div');
  detail.className = 'room-detail';

  const renameButton = document.createElement('button');
  renameButton.type = 'button';
  renameButton.className = 'rename-room-button';
  renameButton.textContent = t('action.renameRoom');
  renameButton.dataset.renameRoom = String(roomId);
  renameButton.addEventListener('click', () => options.onRenameRoom(roomId));
  detail.appendChild(renameButton);

  return detail;
}

function renderPlantTile(
  plant: PlantOut,
  now: Date,
  onWaterPlant: (plantId: number) => void,
  options: RenderAppOptions,
): HTMLElement {
  const tile = document.createElement('article');
  tile.className = 'plant-tile' + (plant.is_overdue ? ' overdue' : '');

  const photo = document.createElement('img');
  // Memory-friendliness (see TODO.md): request a small server-generated
  // thumbnail instead of decoding the full up-to-1280px upload for a tile
  // that only ever displays it at 64x64 CSS px (see .plant-tile img in
  // style.css) — see app.services.thumbnails for why this matters for
  // avoiding Android's low-memory tab discard/reload while the camera is open.
  photo.src = `/photos/thumbnails/${plant.photo_path}`;
  photo.alt = plant.nickname;
  photo.loading = 'lazy';
  photo.decoding = 'async';
  // Falls back to the full photo if thumbnail generation failed server-side
  // (e.g. an undecodable source image) so a plant's photo never silently
  // disappears; `{ once: true }` avoids looping if that also 404s.
  photo.addEventListener('error', () => { photo.src = `/photos/${plant.photo_path}`; }, { once: true });
  tile.appendChild(photo);

  const info = document.createElement('div');
  info.className = 'plant-info';

  const name = document.createElement('h3');
  name.className = 'plant-name';
  name.textContent = plant.nickname;
  info.appendChild(name);

  const due = document.createElement('span');
  due.className = 'due-label';
  due.textContent = dueLabel(plant.next_due_at, now);
  info.appendChild(due);

  tile.appendChild(info);

  const waterButton = document.createElement('button');
  waterButton.className = 'water-button';
  waterButton.textContent = t('action.water');
  waterButton.dataset.waterPlant = String(plant.id);
  waterButton.addEventListener('click', () => onWaterPlant(plant.id));
  tile.appendChild(waterButton);

  const detailToggle = document.createElement('button');
  detailToggle.className = 'detail-toggle';
  detailToggle.textContent = '⋮';
  detailToggle.setAttribute('aria-label', t('action.moreOptions'));
  detailToggle.dataset.detailPlant = String(plant.id);
  detailToggle.addEventListener('click', () => options.onToggleDetail(plant.id));
  tile.appendChild(detailToggle);

  if (options.expandedPlantId === plant.id) {
    const detail = document.createElement('div');
    detail.className = 'plant-detail';
    renderCadenceEditor(
      detail,
      plant,
      { effectiveIntervalDays: plant.recommended_interval_days, source: plant.care_source },
      {
        onSetDays: (days) => options.onSetIntervalDays(plant.id, days),
        onReset: () => options.onResetInterval(plant.id),
      },
    );
    renderCareInfo(detail, plant);

    const actions = document.createElement('div');
    actions.className = 'plant-detail-actions';
    actions.appendChild(renderChangePhotoControl(plant, options));
    actions.appendChild(renderRenameNicknameControl(plant, options));
    const moveRoomControl = renderMoveRoomControl(plant, options);
    if (moveRoomControl) actions.appendChild(moveRoomControl);
    detail.appendChild(actions);

    const removeButton = document.createElement('button');
    removeButton.className = 'remove-button';
    removeButton.textContent = t('action.removePlant');
    removeButton.dataset.removePlant = String(plant.id);
    removeButton.addEventListener('click', () => options.onRemovePlant(plant.id));
    detail.appendChild(removeButton);

    tile.appendChild(detail);
  }

  return tile;
}

function createEmptyStateIcon(): SVGSVGElement {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.classList.add('empty-state-icon');
  svg.setAttribute('viewBox', '0 0 24 24');
  svg.setAttribute('fill', 'none');
  svg.setAttribute('aria-hidden', 'true');

  const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
  path.setAttribute('d', 'M12 2.5c3.5 4.8 7 8.9 7 12.9a7 7 0 1 1-14 0c0-4 3.5-8.1 7-12.9Z');
  path.setAttribute('stroke', 'currentColor');
  path.setAttribute('stroke-width', '1.5');
  path.setAttribute('stroke-linejoin', 'round');
  svg.appendChild(path);

  return svg;
}

/**
 * "Change photo" (TODO.md: "Option to add new picture for the plant"), tucked
 * inside the plant's "⋮" detail menu since it's not something done
 * frequently — a plain file input triggered via a styled label/button, same
 * pattern as the main add-plant capture button (see addPlantUi.ts).
 */
function renderChangePhotoControl(plant: PlantOut, options: RenderAppOptions): HTMLElement {
  const wrapper = document.createElement('div');
  wrapper.className = 'change-photo-control';

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'change-photo-button';
  button.textContent = t('action.changePhoto');
  button.dataset.changePhoto = String(plant.id);

  const input = document.createElement('input');
  input.type = 'file';
  input.accept = 'image/*';
  input.setAttribute('capture', 'environment');
  input.style.display = 'none';

  input.addEventListener('change', () => {
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    options.onChangePhoto(plant.id, file);
  });

  button.addEventListener('click', () => input.click());

  wrapper.appendChild(button);
  wrapper.appendChild(input);
  return wrapper;
}

/**
 * "Rename plant/nickname" (TODO.md), tucked inside the "⋮" detail menu next
 * to "Change photo" — also not something done frequently. The label
 * distinguishes a plant that's still on its auto-derived "{species} #N"
 * name ("Add nickname") from one the user already personalized ("Update
 * nickname"), per plant.nickname_is_custom.
 */
function renderRenameNicknameControl(plant: PlantOut, options: RenderAppOptions): HTMLElement {
  const wrapper = document.createElement('div');
  wrapper.className = 'rename-nickname-control';

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'rename-nickname-button';
  button.textContent = plant.nickname_is_custom ? t('action.updateNickname') : t('action.addNickname');
  button.dataset.renameNickname = String(plant.id);
  button.addEventListener('click', () => options.onRenameNickname(plant.id));

  wrapper.appendChild(button);
  return wrapper;
}

/**
 * "Move plant to different room" (TODO.md), tucked inside the "⋮" detail
 * menu alongside the other rarely-used actions — moving a plant between
 * rooms isn't something done frequently, so it shouldn't clutter the tile.
 * Hidden entirely when there's no other room to move to. Opens a popup
 * (moveRoomUi.ts) listing the other rooms to choose from, rather than
 * cluttering the tile with an inline select list.
 */
function renderMoveRoomControl(plant: PlantOut, options: RenderAppOptions): HTMLElement | null {
  const otherRooms = options.rooms.filter((room) => room.id !== plant.room_id);
  if (otherRooms.length === 0) return null;

  const wrapper = document.createElement('div');
  wrapper.className = 'move-room-control';

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'move-room-button';
  button.textContent = t('action.moveToRoom');
  button.dataset.moveToRoom = String(plant.id);
  button.addEventListener('click', () => options.onOpenMoveRoom(plant.id));
  wrapper.appendChild(button);

  return wrapper;
}
