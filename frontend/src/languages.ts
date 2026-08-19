export const DEFAULT_LOCALE = 'en' as const;

export const SUPPORTED_LOCALES = ['en', 'hu'] as const;

export type Locale = (typeof SUPPORTED_LOCALES)[number];

const SUPPORTED_LOCALE_SET = new Set<string>(SUPPORTED_LOCALES);

export function isSupportedLocale(locale: string): locale is Locale {
  return SUPPORTED_LOCALE_SET.has(locale);
}

export function resolveLocale(candidate: string | undefined | null): Locale | null {
  if (!candidate) return null;

  const primaryTag = candidate.toLowerCase().split('-')[0];
  return isSupportedLocale(primaryTag) ? primaryTag : null;
}
