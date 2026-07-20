export interface LocalSettings {
  download_output_root: string;
}

export class SettingsApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "SettingsApiError";
    this.code = code;
    this.status = status;
  }
}

export async function getLocalSettings(signal?: AbortSignal): Promise<LocalSettings> {
  return requestSettings("/api/settings", "GET", signal);
}

export async function chooseDownloadDirectory(
  signal?: AbortSignal,
): Promise<LocalSettings> {
  return requestSettings("/api/settings/download-directory/choose", "POST", signal);
}

async function requestSettings(
  url: string,
  method: "GET" | "POST",
  signal?: AbortSignal,
): Promise<LocalSettings> {
  const response = await fetch(url, {
    method,
    headers: { Accept: "application/json" },
    signal,
  });
  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) throw toSettingsApiError(payload, response.status);
  if (!isLocalSettings(payload)) {
    throw new SettingsApiError(
      "La respuesta del backend no tiene el formato esperado.",
      "invalid_response",
      response.status,
    );
  }
  return payload;
}

function toSettingsApiError(payload: unknown, status: number): SettingsApiError {
  if (isRecord(payload) && isRecord(payload.error)) {
    const { code, message } = payload.error;
    if (typeof code === "string" && typeof message === "string") {
      return new SettingsApiError(message, code, status);
    }
  }
  return new SettingsApiError(
    "No se ha podido cambiar la carpeta de descargas.",
    "unknown_error",
    status,
  );
}

function isLocalSettings(value: unknown): value is LocalSettings {
  return isRecord(value) && typeof value.download_output_root === "string";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
