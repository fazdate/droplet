/**
 * Minimal i18n helper.
 *
 * The UI language is derived once from the phone/browser locale
 * (`navigator.language(s)`); there is no in-app language switcher by design
 * (see TODO.md — no need to support dynamic changes).
 */

import { DEFAULT_LOCALE, resolveLocale, type Locale } from './languages';

type Dict = Record<string, string>;

const en: Dict = {
  'action.water': 'Water',
  'action.waterAll': 'Water all',
  'action.cancel': 'Cancel',
  'action.addPlant': 'Add plant',
  'action.addRoom': 'Add room',
  'action.search': 'Search',
  'action.yes': 'Yes',
  'action.no': 'No',
  'action.continue': 'Continue',
  'action.undo': 'Undo',
  'action.removePlant': 'Remove plant',
  'action.removeRoom': 'Remove room',
  'action.renameRoom': 'Rename room',
  'action.changePhoto': 'Change photo',
  'action.addNickname': 'Add nickname',
  'action.updateNickname': 'Update nickname',
  'action.moveToRoom': 'Move to room',
  'action.moreOptions': 'More options',
  'action.decreaseInterval': 'Water less often',
  'action.increaseInterval': 'Water more often',
  'action.diagnose': 'Diagnose plant issue',
  'action.quickActions': 'Quick actions',
  'action.tryAgain': 'Try again',
  'action.addManually': 'Add manually',

  'due.notScheduled': 'not scheduled',
  'due.today': 'Water today',
  'due.lateOne': '1 day late',
  'due.lateMany': '{count} days late',
  'due.inOne': 'in 1 day',
  'due.inMany': 'in {count} days',

  'toast.watered': 'Watered',
  'toast.wateredPlants': 'Watered {count} plants',
  'toast.plantRemoved': '{name} removed',
  'toast.roomRemoved': '{name} removed',
  'toast.roomRenamed': 'Room renamed to {name}',
  'toast.photoChanged': 'Photo updated',
  'toast.nicknameUpdated': 'Nickname updated',
  'toast.plantMoved': 'Moved to {room}',
  'toast.roomCreated': 'Room created: {name}',
  'toast.intervalUpdated': 'Watering every {days} days',
  'toast.intervalReset': 'Reset to recommended schedule',

  'error.loadPlants': 'Could not load plants. Is the backend reachable?',
  'error.identify': 'Could not identify this photo. Try again or enter it manually.',
  'error.saveManual': 'Could not save this plant. Please try again.',
  'error.createPlant': 'Could not create the plant. Please try again.',
  'error.removePlant': 'Could not remove this plant. Please try again.',
  'error.removeRoom': 'Could not remove this room. Please try again.',
  'error.createRoom': 'Could not create this room. Please try again.',
  'error.renameRoom': 'Could not rename this room. Please try again.',
  'error.changePhoto': 'Could not update the photo. Please try again.',
  'error.updateNickname': 'Could not update the nickname. Please try again.',
  'error.moveToRoom': 'Could not move this plant. Please try again.',
  'error.captureInterrupted':
    'The camera closed the app in the background to free up memory, so the photo was lost. Please try again.',
  'error.diagnose': 'Could not diagnose this photo. Please try again.',
  'error.diagnoseUnavailable': 'Diagnosis is temporarily unavailable. Please try again later.',
  'error.waterPlant': 'Could not water this plant. Please try again.',
  'error.waterRoom': 'Could not water the plants in this room. Please try again.',
  'error.undo': 'Could not undo the watering. Please try again.',
  'error.setInterval': 'Could not update the watering interval. Please try again.',
  'error.resetInterval': 'Could not reset the watering interval. Please try again.',

  'empty.noPlants': 'No plants yet — tap + to add your first one.',
  'summary.attentionOne': '1 plant needs attention',
  'summary.attentionMany': '{count} plants need attention',
  'room.needWater': '{count} need water',
  'room.addPrompt': 'What would you like to call the new room?',

  'source.perenual': 'recommended (Perenual)',
  'source.llm': 'recommended (AI)',
  'source.default': 'recommended (default)',
  'source.manual': 'set by you',

  'cadence.waterEvery': 'Water every {days} days',
  'cadence.reset': 'Reset to recommended',
  'cadence.resetWithDays': 'Reset to recommended: {days} days',

  'care.heading': 'Care instructions',
  'care.light': 'Light',
  'care.soil': 'Soil',
  'care.notes': 'Notes',
  'care.unavailable': 'No care details available yet for this plant.',

  'modal.identifying': 'Identifying your plant…',
  'modal.isThis': 'Is this a {name}?',

  'manual.searchPrompt': "What do you call it? Search first — we'll try to find its care info.",
  'manual.namePlaceholder': 'What do you call it?',
  'manual.searching': 'Searching…',
  'manual.noResults': 'No matches found — add it manually below.',
  'manual.divider': "Can't find it? Set a watering interval and add it manually:",

  'interval.every4Days': 'every 4 days',
  'interval.weekly': 'weekly',
  'interval.every2Weeks': 'every 2 weeks',

  'roomPicker.newRoomOption': 'New room…',
  'roomPicker.newRoomPlaceholder': 'New room name',
  'roomPicker.noRoomsYet': 'You do not have any rooms yet. Create one below to continue.',
  'roomPicker.moveTitle': 'Move {name} to which room?',
  'roomPicker.noOtherRooms': 'There are no other rooms to move this plant to.',
  'chooser.title': 'What would you like to do?',

  'nickname.prompt': 'Want to give this {name} a nickname?',
  'nickname.placeholder': 'e.g. Fred',
  'nickname.renamePrompt': 'What would you like to call this plant?',
  'room.renamePrompt': 'What would you like to call this room?',
  'room.renameSubmit': 'Rename room',

  'confirm.removePlant': 'Remove {name} and its watering history? This cannot be undone.',
  'confirm.removeRoom': 'Remove the room "{name}"? This cannot be undone.',

  'diagnose.title': 'Diagnose {name}',
  'diagnose.loading': 'Looking for issues…',
  'diagnose.healthy': 'Your plant looks healthy! No issues found.',
  'diagnose.done': 'Done',
  'diagnose.pickPlantPrompt': 'Which plant is this for?',
  'diagnose.noPlantsYet': 'You do not have any plants yet — add one first.',
};

const hu: Dict = {
  'action.water': 'Locsolás',
  'action.waterAll': 'Mindet megöntözöm',
  'action.cancel': 'Mégse',
  'action.addPlant': 'Növény hozzáadása',
  'action.addRoom': 'Szoba hozzáadása',
  'action.search': 'Keresés',
  'action.yes': 'Igen',
  'action.no': 'Nem',
  'action.continue': 'Tovább',
  'action.undo': 'Visszavonás',
  'action.removePlant': 'Növény eltávolítása',
  'action.removeRoom': 'Szoba eltávolítása',
  'action.renameRoom': 'Szoba átnevezése',
  'action.changePhoto': 'Fotó cseréje',
  'action.addNickname': 'Becenév hozzáadása',
  'action.updateNickname': 'Becenév módosítása',
  'action.moveToRoom': 'Áthelyezés másik szobába',
  'action.moreOptions': 'További lehetőségek',
  'action.decreaseInterval': 'Ritkábban locsolva',
  'action.increaseInterval': 'Gyakrabban locsolva',
  'action.diagnose': 'Növény problémáinak diagnosztizálása',
  'action.quickActions': 'Gyors műveletek',
  'action.tryAgain': 'Újra próbálkozás',
  'action.addManually': 'Manuális hozzáadás',

  'due.notScheduled': 'nincs ütemezve',
  'due.today': 'Ma locsolni kell',
  'due.lateOne': '1 napja késik',
  'due.lateMany': '{count} napja késik',
  'due.inOne': '1 nap múlva',
  'due.inMany': '{count} nap múlva',

  'toast.watered': 'Megöntözve',
  'toast.wateredPlants': '{count} növény megöntözve',
  'toast.plantRemoved': '{name} eltávolítva',
  'toast.roomRemoved': '{name} eltávolítva',
  'toast.roomRenamed': 'A szoba átnevezve: {name}',
  'toast.photoChanged': 'Fotó frissítve',
  'toast.nicknameUpdated': 'Becenév frissítve',
  'toast.plantMoved': 'Áthelyezve ide: {room}',
  'toast.roomCreated': 'Szoba létrehozva: {name}',
  'toast.intervalUpdated': 'Locsolás {days} naponta',
  'toast.intervalReset': 'Visszaállítva az ajánlott ütemezésre',

  'error.loadPlants': 'Nem sikerült betölteni a növényeket. Elérhető a szerver?',
  'error.identify': 'Nem sikerült azonosítani a fotót. Próbáld újra, vagy add meg manuálisan.',
  'error.saveManual': 'Nem sikerült menteni a növényt. Próbáld újra.',
  'error.createPlant': 'Nem sikerült létrehozni a növényt. Próbáld újra.',
  'error.removePlant': 'Nem sikerült eltávolítani a növényt. Próbáld újra.',
  'error.removeRoom': 'Nem sikerült eltávolítani a szobát. Próbáld újra.',
  'error.createRoom': 'Nem sikerült létrehozni a szobát. Próbáld újra.',
  'error.renameRoom': 'Nem sikerült átnevezni a szobát. Próbáld újra.',
  'error.changePhoto': 'Nem sikerült frissíteni a fotót. Próbáld újra.',
  'error.updateNickname': 'Nem sikerült frissíteni a becenevet. Próbáld újra.',
  'error.moveToRoom': 'Nem sikerült áthelyezni a növényt. Próbáld újra.',
  'error.captureInterrupted':
    'A böngésző a háttérben bezárta az appot, hogy memóriát szabadítson fel, ezért a fotó elveszett. Próbáld újra.',
  'error.diagnose': 'Nem sikerült elemezni a fotót. Próbáld újra.',
  'error.diagnoseUnavailable': 'A diagnosztika átmenetileg nem elérhető. Próbáld újra később.',
  'error.waterPlant': 'Nem sikerült megöntözni a növényt. Próbáld újra.',
  'error.waterRoom': 'Nem sikerült a szoba növényeit megöntözni. Próbáld újra.',
  'error.undo': 'Nem sikerült visszavonni a locsolást. Próbáld újra.',
  'error.setInterval': 'Nem sikerült frissíteni a locsolás gyakoriságát. Próbáld újra.',
  'error.resetInterval': 'Nem sikerült visszaállítani a locsolás gyakoriságát. Próbáld újra.',

  'empty.noPlants': 'Még nincs növényed — koppints a + gombra az elsőhöz.',
  'summary.attentionOne': '1 növény figyelmet igényel',
  'summary.attentionMany': '{count} növény figyelmet igényel',
  'room.needWater': '{count} locsolásra vár',
  'room.addPrompt': 'Hogyan hívnád az új szobát?',

  'source.perenual': 'ajánlott (Perenual)',
  'source.llm': 'ajánlott (AI)',
  'source.default': 'ajánlott (alapértelmezett)',
  'source.manual': 'általad beállítva',

  'cadence.waterEvery': 'Locsolás {days} naponta',
  'cadence.reset': 'Visszaállítás az ajánlottra',
  'cadence.resetWithDays': 'Visszaállítás az ajánlottra: {days} nap',

  'care.heading': 'Gondozási útmutató',
  'care.light': 'Fény',
  'care.soil': 'Talaj',
  'care.notes': 'Megjegyzések',
  'care.unavailable': 'Ehhez a növényhez még nincs elérhető gondozási információ.',

  'modal.identifying': 'Növény azonosítása…',
  'modal.isThis': 'Ez egy {name}?',

  'manual.searchPrompt': 'Hogy hívod? Keress rá először — megpróbáljuk megtalálni a gondozási adatait.',
  'manual.namePlaceholder': 'Hogy hívod?',
  'manual.searching': 'Keresés…',
  'manual.noResults': 'Nincs találat — add hozzá manuálisan alább.',
  'manual.divider': 'Nem találod? Állíts be egy locsolási gyakoriságot, és add hozzá manuálisan:',

  'interval.every4Days': '4 naponta',
  'interval.weekly': 'hetente',
  'interval.every2Weeks': '2 hetente',

  'roomPicker.newRoomOption': 'Új szoba…',
  'roomPicker.newRoomPlaceholder': 'Új szoba neve',
  'roomPicker.noRoomsYet': 'Még nincs szobád. Az alábbi mezőben hozz létre egyet a folytatáshoz.',
  'roomPicker.moveTitle': 'Melyik szobába kerüljön a(z) {name}?',
  'roomPicker.noOtherRooms': 'Nincs másik szoba, ahova át lehetne helyezni ezt a növényt.',
  'chooser.title': 'Mit szeretnél tenni?',

  'nickname.prompt': 'Adnál a(z) {name} növénynek becenevet?',
  'nickname.placeholder': 'pl. Frédi',
  'nickname.renamePrompt': 'Minek szeretnéd hívni ezt a növényt?',
  'room.renamePrompt': 'Minek szeretnéd hívni ezt a szobát?',
  'room.renameSubmit': 'Szoba átnevezése',

  'confirm.removePlant': 'Eltávolítod a(z) {name} növényt a locsolási előzményeivel együtt? Ez nem vonható vissza.',
  'confirm.removeRoom': 'Eltávolítod a(z) "{name}" szobát? Ez nem vonható vissza.',

  'diagnose.title': '{name} diagnosztizálása',
  'diagnose.loading': 'Problémák keresése…',
  'diagnose.healthy': 'A növényed egészségesnek tűnik! Nem találtunk problémát.',
  'diagnose.done': 'Kész',
  'diagnose.pickPlantPrompt': 'Melyik növényről van szó?',
  'diagnose.noPlantsYet': 'Még nincs növényed — előbb adj hozzá egyet.',
};

const dictionaries: Record<Locale, Dict> = { en, hu };

export function detectLocale(): Locale {
  if (typeof navigator === 'undefined') return DEFAULT_LOCALE;
  const candidates = navigator.languages?.length ? navigator.languages : [navigator.language];
  for (const candidate of candidates) {
    const locale = resolveLocale(candidate);
    if (locale) return locale;
  }
  return DEFAULT_LOCALE;
}

/** Resolved once at startup from the phone/browser locale — no dynamic switching. */
export const locale: Locale = detectLocale();

export function t(key: keyof typeof en, params?: Record<string, string | number>): string {
  const template = dictionaries[locale][key] ?? en[key] ?? key;
  if (!params) return template;
  return Object.entries(params).reduce(
    (result, [paramKey, value]) => result.replaceAll(`{${paramKey}}`, String(value)),
    template,
  );
}
