import type { PlantOut } from './api';
import { t } from './i18n';

/**
 * Plant detail "Care instructions" block — plan TODO: "Provide some care
 * instructions for the plant, such as watering frequency, sunlight needs,
 * etc." Watering frequency already has its own control (see
 * cadenceEditor.ts); this renders the remaining species-level guidance
 * (light/soil/notes) resolved server-side (Perenual -> LLM -> defaults, see
 * app.services.care_resolution), in whatever language the deployment is
 * configured for.
 *
 * Any of the three fields can be null (e.g. a manually-added species, or a
 * lookup that genuinely found nothing) — those rows are simply omitted, and
 * a fallback message shows only when all three are missing.
 */
export function renderCareInfo(container: HTMLElement, plant: PlantOut): void {
  const wrapper = document.createElement('div');
  wrapper.className = 'care-info';

  const heading = document.createElement('h4');
  heading.className = 'care-info-heading';
  heading.textContent = t('care.heading');
  wrapper.appendChild(heading);

  const fields: Array<{ labelKey: 'care.light' | 'care.soil' | 'care.notes'; value: string | null; className: string }> = [
    { labelKey: 'care.light', value: plant.light, className: 'care-light' },
    { labelKey: 'care.soil', value: plant.soil, className: 'care-soil' },
    { labelKey: 'care.notes', value: plant.notes, className: 'care-notes' },
  ];

  const presentFields = fields.filter((field) => field.value);
  if (presentFields.length === 0) {
    const empty = document.createElement('p');
    empty.className = 'care-info-empty';
    empty.textContent = t('care.unavailable');
    wrapper.appendChild(empty);
    container.appendChild(wrapper);
    return;
  }

  for (const field of presentFields) {
    const row = document.createElement('p');
    row.className = `care-info-row ${field.className}`;

    const label = document.createElement('strong');
    label.textContent = `${t(field.labelKey)}: `;
    row.appendChild(label);
    row.appendChild(document.createTextNode(field.value!));

    wrapper.appendChild(row);
  }

  container.appendChild(wrapper);
}
