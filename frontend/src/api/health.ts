export type HealthStatus = "checking" | "connected" | "disconnected";

interface HealthResponse {
  status: "ok";
  service: "video-downloader-api";
}

export async function checkBackendHealth(signal?: AbortSignal): Promise<boolean> {
  const response = await fetch("/health", {
    method: "GET",
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok) {
    return false;
  }

  const payload: unknown = await response.json();
  return isHealthResponse(payload);
}

function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const candidate = value as Record<string, unknown>;
  return candidate.status === "ok" && candidate.service === "video-downloader-api";
}
