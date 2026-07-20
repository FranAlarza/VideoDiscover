export type Platform = "youtube" | "tiktok";

export interface MediaInspection {
  platform: Platform;
  media_id: string;
  title: string;
  author: string | null;
  duration_seconds: number | null;
  thumbnail_url: string | null;
  published_at: string | null;
  estimated_size: number | null;
  video_qualities: number[];
  audio_available: boolean;
  is_live: boolean;
}

interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
  };
}

export class MediaApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "MediaApiError";
    this.code = code;
    this.status = status;
  }
}

export async function inspectMedia(
  url: string,
  signal?: AbortSignal,
): Promise<MediaInspection> {
  const response = await fetch("/api/media/inspect", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ url }),
    signal,
  });

  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw toMediaApiError(payload, response.status);
  }

  if (!isMediaInspection(payload)) {
    throw new MediaApiError(
      "La respuesta del backend no tiene el formato esperado.",
      "invalid_response",
      response.status,
    );
  }

  return payload;
}

function toMediaApiError(payload: unknown, status: number): MediaApiError {
  if (isApiErrorResponse(payload)) {
    return new MediaApiError(payload.error.message, payload.error.code, status);
  }

  return new MediaApiError(
    "No se ha podido analizar la URL. Prueba otra vez en unos segundos.",
    "unknown_error",
    status,
  );
}

function isApiErrorResponse(value: unknown): value is ApiErrorResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const error = (value as Record<string, unknown>).error;
  if (typeof error !== "object" || error === null) {
    return false;
  }

  const candidate = error as Record<string, unknown>;
  return typeof candidate.code === "string" && typeof candidate.message === "string";
}

function isMediaInspection(value: unknown): value is MediaInspection {
  if (typeof value !== "object" || value === null) {
    return false;
  }

  const candidate = value as Record<string, unknown>;

  return (
    isPlatform(candidate.platform) &&
    typeof candidate.media_id === "string" &&
    typeof candidate.title === "string" &&
    isNullableString(candidate.author) &&
    isNullableNumber(candidate.duration_seconds) &&
    isNullableString(candidate.thumbnail_url) &&
    isNullableString(candidate.published_at) &&
    isNullableNumber(candidate.estimated_size) &&
    Array.isArray(candidate.video_qualities) &&
    candidate.video_qualities.every((quality) => typeof quality === "number") &&
    typeof candidate.audio_available === "boolean" &&
    typeof candidate.is_live === "boolean"
  );
}

function isPlatform(value: unknown): value is Platform {
  return value === "youtube" || value === "tiktok";
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || typeof value === "number";
}
