import { afterEach, describe, expect, it, vi } from 'vitest';
import { resizeImageForUpload } from '../src/imageResize';

function fakeBitmap(width: number, height: number): ImageBitmap {
  return { width, height, close: vi.fn() } as unknown as ImageBitmap;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('resizeImageForUpload', () => {
  it('should_return_original_file_untouched_for_non_image_type', async () => {
    const file = new File(['pdf-bytes'], 'doc.pdf', { type: 'application/pdf' });

    const result = await resizeImageForUpload(file);

    expect(result).toBe(file);
  });

  it('should_return_original_file_untouched_for_svg', async () => {
    const file = new File(['<svg/>'], 'plant.svg', { type: 'image/svg+xml' });

    const result = await resizeImageForUpload(file);

    expect(result).toBe(file);
  });

  it('should_return_original_file_when_already_within_max_dimension', async () => {
    const file = new File(['jpeg-bytes'], 'plant.jpg', { type: 'image/jpeg' });
    vi.stubGlobal(
      'createImageBitmap',
      vi.fn().mockResolvedValue(fakeBitmap(800, 600)),
    );

    const result = await resizeImageForUpload(file, { maxDimension: 1280 });

    expect(result).toBe(file);
  });

  it('should_return_original_file_when_decoding_fails', async () => {
    const file = new File(['corrupt'], 'plant.jpg', { type: 'image/jpeg' });
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.stubGlobal('createImageBitmap', vi.fn().mockRejectedValue(new Error('decode error')));

    const result = await resizeImageForUpload(file);

    expect(result).toBe(file);
    expect(consoleErrorSpy).toHaveBeenCalledWith('Image resize failed:', expect.any(Error));
  });

  it('should_return_original_file_when_decoding_never_settles', async () => {
    vi.useFakeTimers();
    const file = new File(['slow'], 'plant.jpg', { type: 'image/jpeg' });
    vi.stubGlobal(
      'createImageBitmap',
      vi.fn().mockImplementation(() => new Promise(() => {})),
    );

    const resultPromise = resizeImageForUpload(file);
    await vi.runAllTimersAsync();
    const result = await resultPromise;

    expect(result).toBe(file);
    vi.useRealTimers();
  });

  it('should_downscale_and_reencode_as_jpeg_when_larger_than_max_dimension', async () => {
    const file = new File(['jpeg-bytes'], 'plant.png', { type: 'image/png' });
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue(fakeBitmap(4000, 2000)));

    const drawImage = vi.fn();
    const fakeBlob = new Blob(['resized'], { type: 'image/jpeg' });
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (
      this: HTMLCanvasElement,
      callback: BlobCallback,
    ) {
      callback(fakeBlob);
    });

    const result = await resizeImageForUpload(file, { maxDimension: 1280 });

    // 4000x2000 scaled down to fit within 1280 on the longest side, preserving aspect ratio.
    expect(drawImage).toHaveBeenCalledWith(expect.anything(), 0, 0, 1280, 640);
    expect(result).not.toBe(file);
    expect(result.type).toBe('image/jpeg');
    expect(result.name).toBe('plant.jpg');
  });

  it('should_return_original_file_when_canvas_2d_context_unavailable', async () => {
    const file = new File(['jpeg-bytes'], 'plant.jpg', { type: 'image/jpeg' });
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue(fakeBitmap(4000, 2000)));
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);

    const result = await resizeImageForUpload(file);

    expect(result).toBe(file);
  });

  it('should_return_original_file_when_toBlob_yields_null', async () => {
    const file = new File(['jpeg-bytes'], 'plant.jpg', { type: 'image/jpeg' });
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue(fakeBitmap(4000, 2000)));
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      drawImage: vi.fn(),
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (
      this: HTMLCanvasElement,
      callback: BlobCallback,
    ) {
      callback(null);
    });

    const result = await resizeImageForUpload(file);

    expect(result).toBe(file);
  });

  it('should_log_and_return_original_file_when_resizing_throws', async () => {
    const file = new File(['jpeg-bytes'], 'plant.jpg', { type: 'image/jpeg' });
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue(fakeBitmap(4000, 2000)));
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      drawImage: vi.fn(() => {
        throw new Error('canvas draw failed');
      }),
    } as unknown as CanvasRenderingContext2D);

    const result = await resizeImageForUpload(file);

    expect(result).toBe(file);
    expect(consoleErrorSpy).toHaveBeenCalledWith('Image resize failed:', expect.any(Error));
  });

  it('should_close_the_bitmap_after_processing', async () => {
    const file = new File(['jpeg-bytes'], 'plant.jpg', { type: 'image/jpeg' });
    const bitmap = fakeBitmap(800, 600);
    vi.stubGlobal('createImageBitmap', vi.fn().mockResolvedValue(bitmap));

    await resizeImageForUpload(file);

    expect(bitmap.close).toHaveBeenCalledOnce();
  });
});

describe('resizeImageForUpload on iOS/Safari', () => {
  // A tiny (1300x10, solid-colour) PNG so the base64 fixture stays small
  // while still exceeding the default 1280px maxDimension on its long side.
  const WIDE_PNG_BASE64 =
    'iVBORw0KGgoAAAANSUhEUgAABRQAAAAKCAIAAABKYEXzAAAAUklEQVR42u3XQQEAAATAQETSP4BYCtDgLsJ+y+kOAAAA4FcSAAAAgHkGAAAA8wwAAADmGQAAAMwzAAAAmGcAAAAwzwAAAGCeAQAAwDwDAAAAlwUoIwFAkipexAAAAABJRU5ErkJggg==';

  function widePngFile(name = 'plant.png'): File {
    const bytes = Uint8Array.from(atob(WIDE_PNG_BASE64), (c) => c.charCodeAt(0));
    return new File([bytes], name, { type: 'image/png' });
  }

  function stubUserAgent(userAgent: string): void {
    Object.defineProperty(navigator, 'userAgent', { value: userAgent, configurable: true });
  }

  const originalUserAgent = navigator.userAgent;

  afterEach(() => {
    stubUserAgent(originalUserAgent);
  });

  it('should_decode_via_img_element_instead_of_createImageBitmap_on_iphone_safari', async () => {
    // iOS/Safari's createImageBitmap() can silently draw solid black for
    // camera photos (see comment in imageResize.ts), so on iOS/Safari we must
    // decode through an <img> element instead and never call createImageBitmap.
    stubUserAgent(
      'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
    );
    const createImageBitmapSpy = vi.fn();
    vi.stubGlobal('createImageBitmap', createImageBitmapSpy);

    const drawImage = vi.fn();
    const fakeBlob = new Blob(['resized'], { type: 'image/jpeg' });
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({ drawImage } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (
      this: HTMLCanvasElement,
      callback: BlobCallback,
    ) {
      callback(fakeBlob);
    });

    const result = await resizeImageForUpload(widePngFile(), { maxDimension: 1280 });

    expect(createImageBitmapSpy).not.toHaveBeenCalled();
    // 1300x10 scaled down to fit within 1280 on the longest side.
    expect(drawImage).toHaveBeenCalledWith(expect.anything(), 0, 0, 1280, 10);
    expect(result).not.toBe(undefined);
    expect(result.type).toBe('image/jpeg');
  });

  it('should_decode_via_img_element_on_desktop_safari_too', async () => {
    stubUserAgent(
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15',
    );
    const createImageBitmapSpy = vi.fn();
    vi.stubGlobal('createImageBitmap', createImageBitmapSpy);
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue({
      drawImage: vi.fn(),
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, 'toBlob').mockImplementation(function (
      this: HTMLCanvasElement,
      callback: BlobCallback,
    ) {
      callback(new Blob(['resized'], { type: 'image/jpeg' }));
    });

    await resizeImageForUpload(widePngFile(), { maxDimension: 1280 });

    expect(createImageBitmapSpy).not.toHaveBeenCalled();
  });

  it('should_still_use_createImageBitmap_on_non_ios_non_safari_browsers', async () => {
    stubUserAgent(
      'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36',
    );
    const createImageBitmapSpy = vi.fn().mockResolvedValue(fakeBitmap(800, 600));
    vi.stubGlobal('createImageBitmap', createImageBitmapSpy);

    const file = new File(['jpeg-bytes'], 'plant.jpg', { type: 'image/jpeg' });
    const result = await resizeImageForUpload(file, { maxDimension: 1280 });

    expect(createImageBitmapSpy).toHaveBeenCalledOnce();
    expect(result).toBe(file);
  });

  it('should_return_original_file_when_img_decode_fails_on_ios', async () => {
    stubUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1');
    vi.stubGlobal('createImageBitmap', vi.fn());
    const file = new File(['not-a-real-image'], 'plant.jpg', { type: 'image/jpeg' });

    const result = await resizeImageForUpload(file);

    expect(result).toBe(file);
  });
});
