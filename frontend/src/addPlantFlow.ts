import type { IdentifyCandidate, PlantOut, RoomSummary } from './api';
import { t } from './i18n';

/** Dependencies injected so this module is unit-testable without real fetch/DOM globals. */
export interface AddPlantDeps {
  identifyPhoto: (file: File) => Promise<{ photo_id: string; candidates: IdentifyCandidate[] }>;
  lookupSpecies: (query: string) => Promise<{ candidates: IdentifyCandidate[] }>;
  createManualSpecies: (name: string, intervalDays: number) => Promise<{ species_id: number }>;
  createPlant: (payload: {
    photo_id: string;
    species_id: number;
    room_id: number;
    nickname?: string;
  }) => Promise<PlantOut>;
  createRoom: (name: string) => Promise<RoomSummary>;
}

type Step =
  | { name: 'idle' }
  | { name: 'identifying' }
  | { name: 'candidates'; photoId: string; candidates: IdentifyCandidate[] }
  | { name: 'manual'; photoId: string }
  | { name: 'nickname-prompt'; photoId: string; species_id: number; defaultName: string }
  | { name: 'room-picker'; photoId: string; species_id: number; nickname?: string }
  | { name: 'error'; message: string; photoId?: string };

/**
 * Orchestrates the add-a-plant flow (plan section 4.4): photo -> AI candidates
 * -> confirm/reject -> room -> created. Manual escape hatch never dead-ends.
 * Pure state machine + injected API calls; the caller supplies `render(step)`
 * to actually paint the DOM for the current step.
 */
export class AddPlantFlow {
  private step: Step = { name: 'idle' };
  private readonly deps: AddPlantDeps;
  private readonly render: (step: Step) => void;
  private readonly onPlantCreated: (plant: PlantOut) => void;

  constructor(deps: AddPlantDeps, render: (step: Step) => void, onPlantCreated: (plant: PlantOut) => void) {
    this.deps = deps;
    this.render = render;
    this.onPlantCreated = onPlantCreated;
    this.render(this.step);
  }

  getStep(): Step {
    return this.step;
  }

  private setStep(step: Step): void {
    this.step = step;
    this.render(step);
  }

  async submitPhoto(file: File): Promise<void> {
    this.setStep({ name: 'identifying' });
    try {
      const result = await this.deps.identifyPhoto(file);
      if (result.candidates.length === 0) {
        this.setStep({ name: 'manual', photoId: result.photo_id });
      } else {
        this.setStep({ name: 'candidates', photoId: result.photo_id, candidates: result.candidates });
      }
    } catch (error) {
      // Show error state with photoId empty, allowing user to see what happened
      // and choose to retry or proceed with manual entry.
      this.setStep({ name: 'error', message: t('error.identify'), photoId: '' });
    }
  }

  rejectAllCandidates(): void {
    if (this.step.name !== 'candidates') return;
    this.setStep({ name: 'manual', photoId: this.step.photoId });
  }

  async searchByName(query: string): Promise<IdentifyCandidate[]> {
    const result = await this.deps.lookupSpecies(query);
    return result.candidates;
  }

  chooseCandidate(candidate: IdentifyCandidate): void {
    const photoId = this.step.name === 'candidates' ? this.step.photoId : (this.step as { photoId?: string }).photoId;
    if (!photoId) return;
    this.setStep({
      name: 'nickname-prompt',
      photoId,
      species_id: candidate.species_id,
      defaultName: candidate.common_name ?? candidate.scientific_name,
    });
  }

  async submitManual(name: string, intervalDays: number): Promise<void> {
    if (this.step.name !== 'manual') return;
    const photoId = this.step.photoId;
    try {
      const { species_id } = await this.deps.createManualSpecies(name, intervalDays);
      this.setStep({ name: 'nickname-prompt', photoId, species_id, defaultName: name });
    } catch {
      this.setStep({ name: 'error', message: t('error.saveManual'), photoId });
    }
  }

  /** User opted out of a custom nickname — the plant keeps its species-derived name. */
  skipNickname(): void {
    if (this.step.name !== 'nickname-prompt') return;
    const { photoId, species_id } = this.step;
    this.setStep({ name: 'room-picker', photoId, species_id });
  }

  /** User chose to give the plant a personal nickname (kept separate from its actual name). */
  setNickname(nickname: string): void {
    if (this.step.name !== 'nickname-prompt') return;
    const { photoId, species_id } = this.step;
    const trimmed = nickname.trim();
    this.setStep({ name: 'room-picker', photoId, species_id, nickname: trimmed || undefined });
  }

  async submitRoomAndCreate(roomChoice: { roomId: number } | { newRoomName: string }): Promise<void> {
    if (this.step.name !== 'room-picker') return;
    const { photoId, species_id, nickname } = this.step;

    try {
      const roomId = 'roomId' in roomChoice ? roomChoice.roomId : (await this.deps.createRoom(roomChoice.newRoomName)).id;
      const plant = await this.deps.createPlant({
        photo_id: photoId,
        species_id,
        room_id: roomId,
        nickname,
      });
      this.setStep({ name: 'idle' });
      this.onPlantCreated(plant);
    } catch {
      this.setStep({ name: 'error', message: t('error.createPlant'), photoId });
    }
  }

  /** Recover from an error state by going back to manual mode (if photoId is available) or canceling. */
  retryFromError(): void {
    if (this.step.name !== 'error') return;
    const photoId = this.step.photoId;
    if (photoId) {
      this.setStep({ name: 'manual', photoId });
    } else {
      this.cancel();
    }
  }

  /** Go to manual entry mode when identification fails and no photo ID is available. */
  goToManualFromError(): void {
    if (this.step.name !== 'error') return;
    this.setStep({ name: 'manual', photoId: '' });
  }

  cancel(): void {
    this.setStep({ name: 'idle' });
  }
}
