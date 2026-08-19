import { afterEach, describe, expect, it, vi } from 'vitest';
import { acquireWakeLock, releaseWakeLock } from '../src/wakeLock';

function stubWakeLockApi(wakeLock: unknown): void {
  Object.defineProperty(navigator, 'wakeLock', {
    value: wakeLock,
    configurable: true,
  });
}

function fakeSentinel() {
  const listeners: Array<() => void> = [];
  return {
    release: vi.fn(async () => {
      listeners.forEach((listener) => listener());
    }),
    addEventListener: vi.fn((_type: 'release', listener: () => void) => {
      listeners.push(listener);
    }),
  };
}

describe('wakeLock', () => {
  afterEach(async () => {
    await releaseWakeLock();
    Object.defineProperty(navigator, 'wakeLock', { value: undefined, configurable: true });
  });

  it('should_do_nothing_when_wake_lock_api_is_unsupported', async () => {
    stubWakeLockApi(undefined);

    await expect(acquireWakeLock()).resolves.toBeUndefined();
    await expect(releaseWakeLock()).resolves.toBeUndefined();
  });

  it('should_request_a_screen_wake_lock_when_supported', async () => {
    const sentinel = fakeSentinel();
    const request = vi.fn().mockResolvedValue(sentinel);
    stubWakeLockApi({ request });

    await acquireWakeLock();

    expect(request).toHaveBeenCalledWith('screen');
  });

  it('should_not_request_a_second_lock_while_one_is_already_held', async () => {
    const sentinel = fakeSentinel();
    const request = vi.fn().mockResolvedValue(sentinel);
    stubWakeLockApi({ request });

    await acquireWakeLock();
    await acquireWakeLock();

    expect(request).toHaveBeenCalledTimes(1);
  });

  it('should_release_the_held_lock', async () => {
    const sentinel = fakeSentinel();
    const request = vi.fn().mockResolvedValue(sentinel);
    stubWakeLockApi({ request });

    await acquireWakeLock();
    await releaseWakeLock();

    expect(sentinel.release).toHaveBeenCalled();
  });

  it('should_swallow_errors_when_the_browser_refuses_the_request', async () => {
    const request = vi.fn().mockRejectedValue(new Error('nope'));
    stubWakeLockApi({ request });

    await expect(acquireWakeLock()).resolves.toBeUndefined();
  });
});
