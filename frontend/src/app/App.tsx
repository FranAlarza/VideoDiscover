import { FormEvent, useMemo, useState } from "react";

import { inspectMedia, MediaApiError, type MediaInspection } from "@/api/media";
import { useBackendHealth } from "@/hooks/useBackendHealth";

const statusCopy = {
  checking: "Comprobando backend",
  connected: "Backend conectado",
  disconnected: "Backend no disponible",
} as const;

type InspectState =
  | { status: "idle"; media: null; error: null }
  | { status: "loading"; media: null; error: null }
  | { status: "success"; media: MediaInspection; error: null }
  | { status: "error"; media: null; error: string };

type OutputMode = "video" | "audio";

export function App() {
  const backendStatus = useBackendHealth();
  const [url, setUrl] = useState("");
  const [outputMode, setOutputMode] = useState<OutputMode>("video");
  const [selectedQuality, setSelectedQuality] = useState<number | null>(null);
  const [inspectState, setInspectState] = useState<InspectState>({
    status: "idle",
    media: null,
    error: null,
  });

  const qualityOptions = useMemo(
    () => sortQualities(inspectState.media?.video_qualities ?? []),
    [inspectState.media],
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedUrl = url.trim();

    if (!trimmedUrl) {
      setInspectState({
        status: "error",
        media: null,
        error: "Pega una URL de YouTube o TikTok para analizarla.",
      });
      return;
    }

    setInspectState({ status: "loading", media: null, error: null });

    try {
      const media = await inspectMedia(trimmedUrl);
      const sortedQualities = sortQualities(media.video_qualities);
      setSelectedQuality(sortedQualities[0] ?? null);
      setOutputMode(media.video_qualities.length > 0 ? "video" : "audio");
      setInspectState({ status: "success", media, error: null });
    } catch (error) {
      const message =
        error instanceof MediaApiError
          ? error.message
          : "No se ha podido conectar con el backend.";
      setInspectState({ status: "error", media: null, error: message });
    }
  }

  const isInspecting = inspectState.status === "loading";
  const canChooseVideo = qualityOptions.length > 0;
  const canChooseAudio = inspectState.media?.audio_available === true;

  return (
    <main className="app-shell">
      <section className="workspace" aria-labelledby="app-title">
        <header className="workspace__header">
          <div>
            <p className="eyebrow">Herramienta local</p>
            <h1 id="app-title">Video Downloader</h1>
            <p className="workspace__description">
              Analiza enlaces públicos y prepara una descarga solo para contenido que
              tengas derecho a guardar.
            </p>
          </div>
          <div className="status" role="status" aria-live="polite">
            <span
              className={`status__dot status__dot--${backendStatus}`}
              aria-hidden="true"
            />
            {statusCopy[backendStatus]}
          </div>
        </header>

        <form
          className="inspect-form"
          onSubmit={(event) => {
            void handleSubmit(event);
          }}
        >
          <label className="field" htmlFor="media-url">
            <span>URL del video</span>
            <input
              id="media-url"
              name="url"
              type="url"
              value={url}
              placeholder="https://www.youtube.com/watch?v=..."
              autoComplete="off"
              onChange={(event) => setUrl(event.target.value)}
              disabled={isInspecting}
            />
          </label>
          <button className="primary-button" type="submit" disabled={isInspecting}>
            {isInspecting ? "Analizando" : "Analizar"}
          </button>
        </form>

        {inspectState.status === "error" ? (
          <div className="notice notice--error" role="alert">
            {inspectState.error}
          </div>
        ) : null}

        {inspectState.status === "loading" ? (
          <div className="notice" role="status" aria-live="polite">
            Obteniendo metadatos sin descargar el archivo...
          </div>
        ) : null}

        {inspectState.media ? (
          <section className="media-panel" aria-labelledby="media-title">
            {inspectState.media.thumbnail_url ? (
              <img
                className="media-panel__thumbnail"
                src={inspectState.media.thumbnail_url}
                alt=""
                loading="lazy"
                referrerPolicy="no-referrer"
              />
            ) : (
              <div className="media-panel__thumbnail media-panel__thumbnail--empty" />
            )}

            <div className="media-panel__content">
              <div className="media-panel__meta">
                <span>{platformCopy[inspectState.media.platform]}</span>
                {inspectState.media.duration_seconds !== null ? (
                  <span>{formatDuration(inspectState.media.duration_seconds)}</span>
                ) : null}
                {inspectState.media.is_live ? <span>Directo</span> : null}
              </div>
              <h2 id="media-title">{inspectState.media.title}</h2>
              {inspectState.media.author ? (
                <p className="media-panel__author">{inspectState.media.author}</p>
              ) : null}

              <div className="output-choice" aria-label="Formato de salida">
                <button
                  type="button"
                  className={outputMode === "video" ? "is-selected" : ""}
                  disabled={!canChooseVideo}
                  onClick={() => setOutputMode("video")}
                >
                  Video
                </button>
                <button
                  type="button"
                  className={outputMode === "audio" ? "is-selected" : ""}
                  disabled={!canChooseAudio}
                  onClick={() => setOutputMode("audio")}
                >
                  Audio
                </button>
              </div>

              {outputMode === "video" && canChooseVideo ? (
                <label className="field field--compact" htmlFor="quality">
                  <span>Calidad</span>
                  <select
                    id="quality"
                    value={selectedQuality ?? ""}
                    onChange={(event) => setSelectedQuality(Number(event.target.value))}
                  >
                    {qualityOptions.map((quality) => (
                      <option key={quality} value={quality}>
                        {quality}p
                      </option>
                    ))}
                  </select>
                </label>
              ) : null}
            </div>
          </section>
        ) : null}
      </section>
    </main>
  );
}

const platformCopy = {
  youtube: "YouTube",
  tiktok: "TikTok",
} as const;

function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function sortQualities(qualities: number[]): number[] {
  return [...qualities].sort((a, b) => b - a);
}
