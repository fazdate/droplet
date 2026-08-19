import type { PlantOut, RoomSummary } from './api';
import { createModalCloseButton } from './addPlantUi';
import { t } from './i18n';

export interface MoveRoomModalOptions {
  plant: PlantOut | null;
  rooms: RoomSummary[];
  onSelectRoom: (roomId: number) => void;
  onCancel: () => void;
}

/**
 * "Move plant to different room" (TODO.md: replace the inline select+button
 * with a popup listing the rooms to choose from) — a small standalone modal,
 * same lightweight overlay pattern as the add-plant modal (see
 * addPlantUi.ts), triggered from the plant detail's "Move to room" button
 * (render.ts).
 */
export function renderMoveRoomModal(container: HTMLElement, options: MoveRoomModalOptions): void {
  container.replaceChildren();
  const { plant } = options;
  if (!plant) {
    container.classList.add('hidden');
    return;
  }
  container.classList.remove('hidden');

  const modal = document.createElement('div');
  modal.className = 'add-plant-modal room-picker-modal';

  modal.appendChild(createModalCloseButton(() => options.onCancel()));

  const title = document.createElement('p');
  title.textContent = t('roomPicker.moveTitle', { name: plant.nickname });
  modal.appendChild(title);

  const otherRooms = options.rooms.filter((room) => room.id !== plant.room_id);

  if (otherRooms.length === 0) {
    const empty = document.createElement('p');
    empty.textContent = t('roomPicker.noOtherRooms');
    modal.appendChild(empty);
  } else {
    const list = document.createElement('div');
    list.className = 'room-picker-list';

    for (const room of otherRooms) {
      const roomButton = document.createElement('button');
      roomButton.type = 'button';
      roomButton.className = 'room-picker-option';
      roomButton.textContent = room.name;
      roomButton.dataset.moveRoomOption = String(room.id);
      roomButton.addEventListener('click', () => options.onSelectRoom(room.id));
      list.appendChild(roomButton);
    }

    modal.appendChild(list);
  }

  container.appendChild(modal);
}
