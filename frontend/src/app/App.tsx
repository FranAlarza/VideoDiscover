import { FormEvent, useEffect, useMemo, useState } from "react";

import {
  subscribeToDownloadEvents,
  type DownloadEventConnectionStatus,
} from "@/api/downloadEvents";
import { createDownload, DownloadApiError, type DownloadTask } from "@/api/downloads";
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

type DownloadState =
  | { status: "idle"; task: null; error: null }
  | { status: "loading"; task: null; error: null }
  | { status: "success"; task: DownloadTask; error: null }
  | { status: "error"; task: null; error: string };

const usageNoticeVersion = "2026-07-20";
const usageNoticeStorageKey = "video-downloader.usage-notice-version";
const usageNotice =
  "Descarga únicamente contenido propio o que tengas derecho a guardar. Esta aplicación no permite eludir DRM, pagos, autenticación ni otros controles de acceso. Tú eres responsable de respetar los derechos de autor, las licencias aplicables y las condiciones de cada plataforma.";

export function App() {
  const backendStatus = useBackendHealth();
  const [url, setUrl] = useState("");
  const [outputMode, setOutputMode] = useState<OutputMode>("video");
  const [selectedQuality, setSelectedQuality] = useState<number | null>(null);
  const [audioBitrate, setAudioBitrate] = useState(192);
  const [showUsageNotice, setShowUsageNotice] = useState(false);
  const [usageNoticeAccepted, setUsageNoticeAccepted] = useState(
    () => readAcceptedUsageNotice() === usageNoticeVersion,
  );
  const [downloadState, setDownloadState] = useState<DownloadState>({
    status: "idle",
    task: null,
    error: null,
  });
  const [downloadEventsStatus, setDownloadEventsStatus] =
    useState<DownloadEventConnectionStatus>("connecting");
  const [inspectState, setInspectState] = useState<InspectState>({
    status: "idle",
    media: null,
    error: null,
  });

  useEffect(() => {
    const client = subscribeToDownloadEvents({
      onTask: (task) => {
        setDownloadState((current) =>
          current.status === "success" && current.task.id === task.id
            ? { ...current, task }
            : current,
        );
      },
      onSnapshot: (tasks) => {
        setDownloadState((current) => {
          if (current.status !== "success") {
            return current;
          }
          const task = tasks.find((candidate) => candidate.id === current.task.id);
          return task ? { ...current, task } : current;
        });
      },
      onConnectionStatus: setDownloadEventsStatus,
    });

    return () => client.close();
  }, []);

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
    setDownloadState({ status: "idle", task: null, error: null });

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

  async function startDownload() {
    if (downloadState.status === "loading" || !inspectState.media) {
      return;
    }
    if (outputMode === "video" && selectedQuality === null) {
      setDownloadState({
        status: "error",
        task: null,
        error: "Selecciona una calidad de vídeo disponible.",
      });
      return;
    }

    setDownloadState({ status: "loading", task: null, error: null });
    try {
      const task = await createDownload({
        url: url.trim(),
        output_type: outputMode,
        video_quality: outputMode === "video" ? selectedQuality : null,
        audio_bitrate: outputMode === "audio" ? audioBitrate : null,
      });
      setDownloadState({ status: "success", task, error: null });
    } catch (error) {
      const message =
        error instanceof DownloadApiError
          ? error.message
          : "No se ha podido conectar con el backend.";
      setDownloadState({ status: "error", task: null, error: message });
    }
  }

  function requestDownload() {
    if (!usageNoticeAccepted) {
      setShowUsageNotice(true);
      return;
    }
    void startDownload();
  }

  function acceptUsageNoticeAndDownload() {
    try {
      window.localStorage.setItem(usageNoticeStorageKey, usageNoticeVersion);
    } catch {
      // The acceptance remains valid for this session if local storage is unavailable.
    }
    setUsageNoticeAccepted(true);
    setShowUsageNotice(false);
    void startDownload();
  }

  const isInspecting = inspectState.status === "loading";
  const canChooseVideo = qualityOptions.length > 0;
  const canChooseAudio = inspectState.media?.audio_available === true;
  const isCreatingDownload = downloadState.status === "loading";

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

              {outputMode === "audio" && canChooseAudio ? (
                <label className="field field--compact" htmlFor="audio-bitrate">
                  <span>Calidad de audio</span>
                  <select
                    id="audio-bitrate"
                    value={audioBitrate}
                    onChange={(event) => setAudioBitrate(Number(event.target.value))}
                  >
                    <option value={128}>128 kbps</option>
                    <option value={192}>192 kbps</option>
                    <option value={320}>320 kbps</option>
                  </select>
                </label>
              ) : null}

              <button
                className="primary-button download-button"
                type="button"
                disabled={isCreatingDownload}
                onClick={requestDownload}
              >
                {isCreatingDownload ? "Iniciando descarga" : "Descargar"}
              </button>
            </div>
          </section>
        ) : null}

        {downloadState.status === "error" ? (
          <div className="notice notice--error" role="alert">
            {downloadState.error}
          </div>
        ) : null}

        {downloadState.status === "success" ? (
          <section className="download-card" aria-labelledby="download-title">
            <div className="download-card__header">
              <p className="eyebrow">Descarga creada</p>
              <h2 id="download-title">{downloadState.task.title}</h2>
            </div>
            <dl className="download-card__stats">
              <div>
                <dt>Estado</dt>
                <dd>{downloadStatusCopy[downloadState.task.status]}</dd>
              </div>
              <div>
                <dt>Formato</dt>
                <dd>{formatSelection(downloadState.task)}</dd>
              </div>
              {downloadState.task.queue_position !== null ? (
                <div>
                  <dt>Posición en cola</dt>
                  <dd>{downloadState.task.queue_position}</dd>
                </div>
              ) : null}
              {visibleProgress(downloadState.task) !== null ? (
                <div>
                  <dt>Progreso</dt>
                  <dd>{formatPercentage(visibleProgress(downloadState.task) ?? 0)}</dd>
                </div>
              ) : null}
            </dl>
            {downloadState.task.current_attempt.result ? (
              <div className="download-card__file">
                <span>Archivo</span>
                <p>{downloadState.task.current_attempt.result.filename}</p>
              </div>
            ) : null}
            {visibleProgress(downloadState.task) !== null ? (
              <progress
                className="download-progress"
                max={100}
                value={visibleProgress(downloadState.task) ?? 0}
                aria-label="Progreso de descarga"
              />
            ) : null}
            {downloadState.task.current_attempt.failure ? (
              <p className="download-card__message" role="alert">
                {downloadState.task.current_attempt.failure.message}
              </p>
            ) : null}
            {downloadEventsStatus === "disconnected" &&
            isActiveDownload(downloadState.task) ? (
              <p className="download-card__message">
                Reconectando con el backend para actualizar el progreso...
              </p>
            ) : null}
          </section>
        ) : null}

        <details className="about">
          <summary>Acerca de y uso responsable</summary>
          <p>{usageNotice}</p>
        </details>
      </section>

      {showUsageNotice ? (
        <div className="dialog-backdrop">
          <section
            className="usage-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="usage-dialog-title"
            aria-describedby="usage-dialog-description"
          >
            <p className="eyebrow">Antes de continuar</p>
            <h2 id="usage-dialog-title">Uso responsable</h2>
            <p id="usage-dialog-description">{usageNotice}</p>
            <div className="usage-dialog__actions">
              <button
                className="secondary-button"
                type="button"
                onClick={() => setShowUsageNotice(false)}
              >
                Ahora no
              </button>
              <button
                className="primary-button"
                type="button"
                onClick={acceptUsageNoticeAndDownload}
              >
                Aceptar y descargar
              </button>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}

const platformCopy = {
  youtube: "YouTube",
  tiktok: "TikTok",
} as const;

const downloadStatusCopy = {
  queued: "En cola",
  downloading: "Descargando",
  processing: "Procesando archivo",
  completed: "Completada",
  failed: "Fallida",
  cancelled: "Cancelada",
  interrupted: "Interrumpida",
} as const;

function formatSelection(task: DownloadTask): string {
  if (task.selection.output_type === "audio") {
    return `MP3 · ${task.selection.audio_bitrate ?? 192} kbps`;
  }
  return `MP4 · ${task.selection.video_quality ?? "mejor"}p`;
}

function formatPercentage(value: number): string {
  return `${Math.round(value)}%`;
}

function visibleProgress(task: DownloadTask): number | null {
  if (task.status === "completed") {
    return 100;
  }
  return task.current_attempt.progress.percentage;
}

function isActiveDownload(task: DownloadTask): boolean {
  return ["queued", "downloading", "processing"].includes(task.status);
}

function readAcceptedUsageNotice(): string | null {
  try {
    return window.localStorage.getItem(usageNoticeStorageKey);
  } catch {
    return null;
  }
}

function formatDuration(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

function sortQualities(qualities: number[]): number[] {
  return [...qualities].sort((a, b) => b - a);
}
