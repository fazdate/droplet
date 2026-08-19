import { afterEach, describe, expect, it, vi } from 'vitest';
import { detectLocale } from '../src/i18n';
import { DEFAULT_LOCALE, SUPPORTED_LOCALES, isSupportedLocale, resolveLocale } from '../src/languages';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('language registry', () => {
  it('should_list_supported_locales', () => {
    expect(SUPPORTED_LOCALES).toEqual(['en', 'hu']);
    expect(isSupportedLocale('hu')).toBe(true);
    expect(resolveLocale('hu-HU')).toBe('hu');
  });

  it('should_return_the_default_locale_when_the_browser_language_is_unknown', () => {
    vi.stubGlobal('navigator', { language: 'de-DE', languages: ['de-DE'] });

    expect(detectLocale()).toBe(DEFAULT_LOCALE);
  });

  it('should_detect_hungarian_from_browser_locale', () => {
    vi.stubGlobal('navigator', { language: 'hu-HU' });

    expect(detectLocale()).toBe('hu');
  });
});
