/**
 * Thin wrapper around the Screen Wake Lock API so the phone/browser screen
 * doesn't fall asleep while a long-running operation (e.g. plant
 * identification) is in progress. Feature-detected and fully optional: on
 * browsers without support this becomes a silent no-op.
 */

interface WakeLockSentinelLike {
  release: () => Promise<void>;
  addEventListener: (type: 'release', listener: () => void) => void;
}

interface NavigatorWithWakeLock {
  wakeLock?: {
    request: (type: 'screen') => Promise<WakeLockSentinelLike>;
  };
}

let sentinel: WakeLockSentinelLike | null = null;
/** Whether we currently want the lock held — used to re-acquire it after the
 * OS releases it automatically when the tab is hidden. */
let wanted = false;

function getWakeLockApi(): NavigatorWithWakeLock['wakeLock'] | undefined {
  if (typeof navigator === 'undefined') return undefined;
  return (navigator as NavigatorWithWakeLock).wakeLock;
}

export async function acquireWakeLock(): Promise<void> {
  wanted = true;
  if (sentinel) return;

  const wakeLock = getWakeLockApi();
  if (!wakeLock) return;

  try {
    sentinel = await wakeLock.request('screen');
    sentinel.addEventListener('release', () => {
      sentinel = null;
    });
  } catch {
    // Wake lock can be refused (e.g. low battery, unsupported context) —
    // that's fine, the animation still shows progress without it.
    sentinel = null;
  }
}

export async function releaseWakeLock(): Promise<void> {
  wanted = false;
  if (!sentinel) return;
  try {
    await sentinel.release();
  } catch {
    // ignore — sentinel may already be released
  }
  sentinel = null;
}

if (typeof document !== 'undefined') {
  document.addEventListener('visibilitychange', () => {
    if (wanted && document.visibilityState === 'visible' && !sentinel) {
      void acquireWakeLock();
    }
  });
}
