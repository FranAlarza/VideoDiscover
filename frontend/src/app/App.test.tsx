import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal("EventSource", FakeEventSource);
    FakeEventSource.instances = [];
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it("shows the application purpose while checking the backend", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => undefined)),
    );

    render(<App />);

    expect(screen.getByRole("heading", { name: "Video Downloader" })).toBeVisible();
    expect(screen.getByLabelText("URL del video")).toBeVisible();
    expect(screen.getByRole("status")).toHaveTextContent("Comprobando backend");
  });

  it("shows the connected state for the exact health contract", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", service: "video-downloader-api" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    expect(await screen.findByText("Backend conectado")).toBeVisible();
    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, options] = fetchMock.mock.calls[0] ?? [];
    expect(url).toBe("/health");
    expect(options?.method).toBe("GET");
    expect(options?.signal).toBeInstanceOf(AbortSignal);
  });

  it.each([
    ["a network failure", () => Promise.reject(new TypeError("Failed to fetch"))],
    [
      "an invalid response",
      () =>
        Promise.resolve(
          new Response(JSON.stringify({ status: "maybe" }), { status: 200 }),
        ),
    ],
  ])("shows the disconnected state for %s", async (_label, response) => {
    vi.stubGlobal("fetch", vi.fn(response));

    render(<App />);

    expect(await screen.findByText("Backend no disponible")).toBeVisible();
  });

  it("inspects a media URL and shows selectable output options", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn<typeof fetch>((input) => {
      if (input === "/health") {
        return Promise.resolve(
          new Response(
            JSON.stringify({ status: "ok", service: "video-downloader-api" }),
            {
              status: 200,
              headers: { "Content-Type": "application/json" },
            },
          ),
        );
      }

      return Promise.resolve(
        new Response(
          JSON.stringify({
            platform: "youtube",
            media_id: "mfqTOAxmhOs",
            title: "Demo descargable",
            author: "Canal demo",
            duration_seconds: 125,
            thumbnail_url: "https://example.com/thumb.jpg",
            published_at: null,
            estimated_size: null,
            video_qualities: [360, 720],
            audio_available: true,
            is_live: false,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);

    await user.type(
      screen.getByLabelText("URL del video"),
      "https://youtu.be/mfqTOAxmhOs",
    );
    await user.click(screen.getByRole("button", { name: "Analizar" }));

    expect(
      await screen.findByRole("heading", { name: "Demo descargable" }),
    ).toBeVisible();
    expect(screen.getByText("Canal demo")).toBeVisible();
    expect(screen.getByText("YouTube")).toBeVisible();
    expect(screen.getByText("2:05")).toBeVisible();
    expect(screen.getByRole("button", { name: "Video" })).toHaveClass("is-selected");
    expect(screen.getByRole("button", { name: "Audio" })).toBeEnabled();
    expect(screen.getByLabelText("Calidad")).toHaveValue("720");
  });

  it("shows a local validation error for an empty URL", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(JSON.stringify({ status: "ok", service: "video-downloader-api" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    render(<App />);

    await user.click(screen.getByRole("button", { name: "Analizar" }));

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Pega una URL de YouTube o TikTok para analizarla.",
    );
  });

  it("shows the backend inspection error message", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>((input) => {
        if (input === "/health") {
          return Promise.resolve(
            new Response(
              JSON.stringify({ status: "ok", service: "video-downloader-api" }),
              {
                status: 200,
                headers: { "Content-Type": "application/json" },
              },
            ),
          );
        }

        return Promise.resolve(
          new Response(
            JSON.stringify({
              error: {
                code: "unsupported_platform",
                message: "Solo se admiten URLs de YouTube y TikTok.",
              },
            }),
            { status: 400, headers: { "Content-Type": "application/json" } },
          ),
        );
      }),
    );

    render(<App />);

    await user.type(screen.getByLabelText("URL del video"), "https://example.com/demo");
    await user.click(screen.getByRole("button", { name: "Analizar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Solo se admiten URLs de YouTube y TikTok.",
    );
  });

  it("requires the usage notice before creating a video download", async () => {
    const user = userEvent.setup();
    const fetchMock = createDownloadFlowMock();
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await inspectDemo(user);
    await user.click(screen.getByRole("button", { name: "Descargar" }));

    expect(screen.getByRole("dialog", { name: "Uso responsable" })).toBeVisible();
    expect(fetchMock).toHaveBeenCalledTimes(2);

    await user.click(screen.getByRole("button", { name: "Aceptar y descargar" }));

    expect(await screen.findByText("En cola")).toBeVisible();
    expect(screen.getByText("MP4 · 720p")).toBeVisible();
    expect(window.localStorage.getItem("video-downloader.usage-notice-version")).toBe(
      "2026-07-20",
    );
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/downloads",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          url: "https://youtu.be/abc123",
          output_type: "video",
          video_quality: 720,
          audio_bitrate: null,
        }),
      }),
    );
  });

  it("updates the download card from backend events", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("video-downloader.usage-notice-version", "2026-07-20");
    const fetchMock = createDownloadFlowMock();
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await inspectDemo(user);
    await user.click(screen.getByRole("button", { name: "Descargar" }));
    await screen.findByText("En cola");

    FakeEventSource.instances[0]?.emit("download.updated", {
      occurred_at: "2026-07-20T16:37:43Z",
      task: {
        ...downloadTask,
        status: "completed",
        queue_position: null,
        current_attempt: {
          ...downloadTask.current_attempt,
          status: "completed",
          progress: {
            percentage: 100,
            downloaded_bytes: 1000000,
            total_bytes: 1000000,
            speed_bytes_per_second: null,
            eta_seconds: null,
          },
          result: {
            filename: "Demo descargable.mp4",
            extension: "mp4",
            size_bytes: 1000000,
            effective_quality: 720,
          },
        },
      },
    });

    expect(await screen.findByText("Completada")).toBeVisible();
    expect(screen.getByText("100%")).toBeVisible();
    expect(screen.getByText("Demo descargable.mp4")).toBeVisible();
  });

  it("keeps completed downloads at 100% when the final event omits progress", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("video-downloader.usage-notice-version", "2026-07-20");
    const fetchMock = createDownloadFlowMock();
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await inspectDemo(user);
    await user.click(screen.getByRole("button", { name: "Descargar" }));
    await screen.findByText("En cola");

    FakeEventSource.instances[0]?.emit("download.updated", {
      occurred_at: "2026-07-20T16:37:43Z",
      task: {
        ...downloadTask,
        status: "completed",
        queue_position: null,
        current_attempt: {
          ...downloadTask.current_attempt,
          status: "completed",
          progress: {
            percentage: null,
            downloaded_bytes: null,
            total_bytes: null,
            speed_bytes_per_second: null,
            eta_seconds: null,
          },
          result: {
            filename:
              "AL BORDE del INFARTO‼️ GRASAS al FALLO y AZÚCARES con 100 PASOS al DÍA😨.mp4",
            extension: "mp4",
            size_bytes: 1000000,
            effective_quality: 1080,
          },
        },
      },
    });

    expect(await screen.findByText("Completada")).toBeVisible();
    expect(screen.getByText("100%")).toBeVisible();
    expect(screen.getByText(/AL BORDE del INFARTO/)).toBeVisible();
    expect(screen.getByLabelText("Progreso de descarga")).toHaveValue(100);
  });

  it("creates an audio download with the selected bitrate", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("video-downloader.usage-notice-version", "2026-07-20");
    const fetchMock = createDownloadFlowMock("audio");
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await inspectDemo(user);
    await user.click(screen.getByRole("button", { name: "Audio" }));
    await user.selectOptions(screen.getByLabelText("Calidad de audio"), "320");
    await user.click(screen.getByRole("button", { name: "Descargar" }));

    expect(await screen.findByText("MP3 · 320 kbps")).toBeVisible();
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/api/downloads",
      expect.objectContaining({
        body: JSON.stringify({
          url: "https://youtu.be/abc123",
          output_type: "audio",
          video_quality: null,
          audio_bitrate: 320,
        }),
      }),
    );
  });

  it("prevents duplicate submissions while creating a download", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("video-downloader.usage-notice-version", "2026-07-20");
    const pendingDownload = new Promise<Response>(() => undefined);
    const fetchMock = createDownloadFlowMock("video", pendingDownload);
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await inspectDemo(user);
    await user.click(screen.getByRole("button", { name: "Descargar" }));

    expect(screen.getByRole("button", { name: "Iniciando descarga" })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });
});

class FakeEventSource extends EventTarget {
  static instances: FakeEventSource[] = [];
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  readonly url: string;

  constructor(url: string | URL) {
    super();
    this.url = url.toString();
    FakeEventSource.instances.push(this);
  }

  close() {
    this.closed = true;
  }

  emit(type: string, data: unknown) {
    this.dispatchEvent(new MessageEvent(type, { data: JSON.stringify(data) }));
  }
}

const inspection = {
  platform: "youtube",
  media_id: "abc123",
  title: "Demo descargable",
  author: "Canal demo",
  duration_seconds: 125,
  thumbnail_url: null,
  published_at: null,
  estimated_size: null,
  video_qualities: [360, 720],
  audio_available: true,
  is_live: false,
};

async function inspectDemo(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("URL del video"), "https://youtu.be/abc123");
  await user.click(screen.getByRole("button", { name: "Analizar" }));
  await screen.findByRole("heading", { name: "Demo descargable" });
}

function createDownloadFlowMock(
  outputType: "video" | "audio" = "video",
  downloadResponse?: Promise<Response>,
) {
  return vi.fn<typeof fetch>((input) => {
    if (input === "/health") {
      return Promise.resolve(
        new Response(JSON.stringify({ status: "ok", service: "video-downloader-api" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    if (input === "/api/media/inspect") {
      return Promise.resolve(
        new Response(JSON.stringify(inspection), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    if (downloadResponse) {
      return downloadResponse;
    }

    return Promise.resolve(
      new Response(
        JSON.stringify({
          ...downloadTask,
          selection: {
            output_type: outputType,
            video_quality: outputType === "video" ? 720 : null,
            audio_bitrate: outputType === "audio" ? 320 : null,
          },
        }),
        { status: 201, headers: { "Content-Type": "application/json" } },
      ),
    );
  });
}

const downloadTask = {
  id: "ad73f0bf-b078-4d21-a4b1-a7517679aec5",
  platform: "youtube",
  media_id: "abc123",
  title: "Demo descargable",
  selection: {
    output_type: "video",
    video_quality: 720,
    audio_bitrate: null,
  },
  status: "queued",
  queue_position: 1,
  created_at: "2026-07-20T16:37:42Z",
  current_attempt: {
    number: 1,
    status: "queued",
    created_at: "2026-07-20T16:37:42Z",
    started_at: null,
    finished_at: null,
    progress: {
      percentage: null,
      downloaded_bytes: null,
      total_bytes: null,
      speed_bytes_per_second: null,
      eta_seconds: null,
    },
    failure: null,
    result: null,
  },
  attempts: [],
};
