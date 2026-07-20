import type { Platform } from "@/api/media";

export type OutputType = "video" | "audio";
export type DownloadStatus =
  | "queued"
  | "downloading"
  | "processing"
  | "completed"
  | "failed"
  | "cancelled"
  | "interrupted";

export interface DownloadCreateRequest {
  url: string;
  output_type: OutputType;
  video_quality: number | null;
  audio_bitrate: number | null;
}

export interface DownloadTask {
  id: string;
  platform: Platform;
  media_id: string;
  title: string;
  selection: {
    output_type: OutputType;
    video_quality: number | null;
    audio_bitrate: number | null;
  };
  status: DownloadStatus;
  queue_position: number | null;
  created_at: string;
  current_attempt: DownloadAttempt;
  attempts: DownloadAttempt[];
}

export interface DownloadAttempt {
  number: number;
  status: DownloadStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  progress: {
    percentage: number | null;
    downloaded_bytes: number | null;
    total_bytes: number | null;
    speed_bytes_per_second: number | null;
    eta_seconds: number | null;
  };
  failure: { code: string; message: string } | null;
  result: {
    filename: string;
    extension: string;
    size_bytes: number;
    effective_quality: number | null;
  } | null;
}

export class DownloadApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "DownloadApiError";
    this.code = code;
    this.status = status;
  }
}

export async function createDownload(
  request: DownloadCreateRequest,
  signal?: AbortSignal,
): Promise<DownloadTask> {
  const response = await fetch("/api/downloads", {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
    signal,
  });
  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw toDownloadApiError(payload, response.status);
  }
  if (!isDownloadTask(payload)) {
    throw new DownloadApiError(
      "La respuesta del backend no tiene el formato esperado.",
      "invalid_response",
      response.status,
    );
  }
  return payload;
}

export async function getDownloads(signal?: AbortSignal): Promise<DownloadTask[]> {
  const response = await fetch("/api/downloads", {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });
  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw toDownloadApiError(payload, response.status);
  }
  if (!isDownloadList(payload)) {
    throw new DownloadApiError(
      "La respuesta del backend no tiene el formato esperado.",
      "invalid_response",
      response.status,
    );
  }
  return payload.items;
}

export async function cancelDownload(
  taskId: string,
  signal?: AbortSignal,
): Promise<DownloadTask> {
  const response = await fetch(`/api/downloads/${encodeURIComponent(taskId)}/cancel`, {
    method: "POST",
    headers: { Accept: "application/json" },
    signal,
  });
  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw toDownloadApiError(payload, response.status);
  }
  if (!isDownloadTask(payload)) {
    throw new DownloadApiError(
      "La respuesta del backend no tiene el formato esperado.",
      "invalid_response",
      response.status,
    );
  }
  return payload;
}

export async function retryDownload(
  taskId: string,
  signal?: AbortSignal,
): Promise<DownloadTask> {
  const response = await fetch(`/api/downloads/${encodeURIComponent(taskId)}/retry`, {
    method: "POST",
    headers: { Accept: "application/json" },
    signal,
  });
  const payload: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    throw toDownloadApiError(payload, response.status);
  }
  if (!isDownloadTask(payload)) {
    throw new DownloadApiError(
      "La respuesta del backend no tiene el formato esperado.",
      "invalid_response",
      response.status,
    );
  }
  return payload;
}

function toDownloadApiError(payload: unknown, status: number): DownloadApiError {
  if (isRecord(payload) && isRecord(payload.error)) {
    const { code, message } = payload.error;
    if (typeof code === "string" && typeof message === "string") {
      return new DownloadApiError(message, code, status);
    }
  }
  return new DownloadApiError(
    "No se ha podido completar la operación. Prueba otra vez.",
    "unknown_error",
    status,
  );
}

export function isDownloadTask(value: unknown): value is DownloadTask {
  if (!isRecord(value) || !isSelection(value.selection)) {
    return false;
  }
  return (
    typeof value.id === "string" &&
    (value.platform === "youtube" || value.platform === "tiktok") &&
    typeof value.media_id === "string" &&
    typeof value.title === "string" &&
    isDownloadStatus(value.status) &&
    (value.queue_position === null || typeof value.queue_position === "number") &&
    typeof value.created_at === "string" &&
    isDownloadAttempt(value.current_attempt) &&
    Array.isArray(value.attempts) &&
    value.attempts.every(isDownloadAttempt)
  );
}

function isDownloadList(value: unknown): value is { items: DownloadTask[] } {
  return (
    isRecord(value) && Array.isArray(value.items) && value.items.every(isDownloadTask)
  );
}

function isSelection(value: unknown): value is DownloadTask["selection"] {
  if (!isRecord(value)) return false;
  return (
    (value.output_type === "video" || value.output_type === "audio") &&
    isNullableNumber(value.video_quality) &&
    isNullableNumber(value.audio_bitrate)
  );
}

function isDownloadAttempt(value: unknown): value is DownloadAttempt {
  if (!isRecord(value) || !isRecord(value.progress)) return false;
  return (
    typeof value.number === "number" &&
    isDownloadStatus(value.status) &&
    typeof value.created_at === "string" &&
    isNullableString(value.started_at) &&
    isNullableString(value.finished_at) &&
    isNullableNumber(value.progress.percentage) &&
    isNullableNumber(value.progress.downloaded_bytes) &&
    isNullableNumber(value.progress.total_bytes) &&
    isNullableNumber(value.progress.speed_bytes_per_second) &&
    isNullableNumber(value.progress.eta_seconds) &&
    (value.failure === null || isRecord(value.failure)) &&
    (value.result === null || isRecord(value.result))
  );
}

function isDownloadStatus(value: unknown): value is DownloadStatus {
  return (
    value === "queued" ||
    value === "downloading" ||
    value === "processing" ||
    value === "completed" ||
    value === "failed" ||
    value === "cancelled" ||
    value === "interrupted"
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNullableNumber(value: unknown): value is number | null {
  return value === null || typeof value === "number";
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}
