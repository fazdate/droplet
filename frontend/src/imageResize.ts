/**
 * Client-side photo resize/compress before upload (plan TODO: speed up plant
 * identification by cutting upload size, and therefore likely inference
 * time, before the photo ever reaches the AI endpoint).
 *
 * Downscales oversized photos to `maxDimension` on their longest side and
 * re-encodes them as JPEG via a canvas. Any failure along the way (missing
 * canvas/decode support, a corrupt/undecodable file, a decode that never
 * settles, ...) falls back to returning the original file untouched so the
 * upload flow never breaks because of this optimization.
 */

const MAX_DIMENSION = 1280;
const JPEG_QUALITY = 0.82;
const DECODE_TIMEOUT_MS = 8000;

export interface ResizeOptions {
  maxDimension?: number;
  quality?: number;
}

function withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('image decode timed out')), ms);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}

// iOS/Safari's createImageBitmap() is unreliable for photos straight out of
// the Camera app (especially large HEIC captures from newer iPhones): it
// resolves without throwing, but drawing the resulting bitmap onto a canvas
// can silently produce solid black pixels instead of the real photo. This is
// a long-standing WebKit bug, which is why widely used image-compression
// libraries deliberately skip createImageBitmap on iOS/Safari and decode
// through an <img> element instead (see e.g.
// https://github.com/Donaldcwl/browser-image-compression/issues/118 and
// .../issues/190). We do the same here so photos taken on an iPhone (front
// or back camera) don't end up uploaded as a black image.
function isIOSOrSafari(): boolean {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator.userAgent || '';
  const isIOSDevice =
    /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const isSafari = /^(?:(?!chrome|android|crios|fxios|edg).)*safari/i.test(ua);
  return isIOSDevice || isSafari;
}

interface DecodedImage {
  source: CanvasImageSource;
  width: number;
  height: number;
  close: () => void;
}

async function decodeViaImageElement(file: File): Promise<DecodedImage> {
  const dataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = () => reject(reader.error ?? new Error('failed to read file'));
    reader.readAsDataURL(file);
  });

  const img = new Image();
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve();
    img.onerror = () => reject(new Error('failed to decode image'));
    img.src = dataUrl;
  });

  return {
    source: img,
    width: img.naturalWidth,
    height: img.naturalHeight,
    close: () => {
      img.src = '';
    },
  };
}

async function decodeViaImageBitmap(file: File): Promise<DecodedImage> {
  const bitmap = await createImageBitmap(file);
  return {
    source: bitmap,
    width: bitmap.width,
    height: bitmap.height,
    close: () => bitmap.close?.(),
  };
}

function decodeImage(file: File): Promise<DecodedImage> {
  return isIOSOrSafari() ? decodeViaImageElement(file) : decodeViaImageBitmap(file);
}

export async function resizeImageForUpload(file: File, options: ResizeOptions = {}): Promise<File> {
  // SVGs (and non-images) aren't raster photos, so there's nothing to
  // downscale — let the backend handle them as-is.
  if (!file.type.startsWith('image/') || file.type === 'image/svg+xml') {
    return file;
  }

  const maxDimension = options.maxDimension ?? MAX_DIMENSION;
  const quality = options.quality ?? JPEG_QUALITY;

  let decoded: DecodedImage;
  try {
    decoded = await withTimeout(decodeImage(file), DECODE_TIMEOUT_MS);
  } catch (err) {
    console.error('Image resize failed:', err);
    return file;
  }

  try {
    if (decoded.width <= maxDimension && decoded.height <= maxDimension) {
      return file; // already small enough, skip re-encoding
    }

    const scale = maxDimension / Math.max(decoded.width, decoded.height);
    const width = Math.max(1, Math.round(decoded.width * scale));
    const height = Math.max(1, Math.round(decoded.height * scale));

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) return file;

    ctx.drawImage(decoded.source, 0, 0, width, height);

    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality));
    if (!blob) return file;

    const resizedName = `${file.name.replace(/\.\w+$/, '')}.jpg`;
    return new File([blob], resizedName, { type: 'image/jpeg' });
  } catch (err) {
    console.error('Image resize failed:', err);
    return file;
  } finally {
    decoded.close();
  }
}
