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
    expect(screen.getByText("Comprobando backend")).toBeVisible();
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
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [url, options] =
      fetchMock.mock.calls.find(([input]) => input === "/health") ?? [];
    expect(url).toBe("/health");
    expect(options?.method).toBe("GET");
    expect(options?.signal).toBeInstanceOf(AbortSignal);
  });

  it("loads and changes the download directory with the native chooser", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn<typeof fetch>((input, init) => {
      if (input === "/health") {
        return Promise.resolve(
          new Response(
            JSON.stringify({ status: "ok", service: "video-downloader-api" }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      if (input === "/api/downloads") {
        return Promise.resolve(
          new Response(JSON.stringify({ items: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      if (input === "/api/settings") {
        return Promise.resolve(
          new Response(
            JSON.stringify({ download_output_root: "/Users/demo/Downloads" }),
            { status: 200, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      if (
        input === "/api/settings/download-directory/choose" &&
        init?.method === "POST"
      ) {
        return Promise.resolve(
          new Response(JSON.stringify({ download_output_root: "/Users/demo/Videos" }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.reject(new Error(`Unexpected request: ${requestUrl(input)}`));
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await user.click(screen.getByText("Configuración"));

    expect(await screen.findByText("/Users/demo/Downloads")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Cambiar carpeta" }));
    expect(await screen.findByText("/Users/demo/Videos")).toBeVisible();
  });

  it("allows the history section to be collapsed", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", createHistoryMock([]));

    render(<App />);
    const historyHeading = screen.getByRole("heading", { name: "Historial" });
    const history = historyHeading.closest("details");

    expect(history).toHaveAttribute("open");
    await user.click(historyHeading);
    expect(history).not.toHaveAttribute("open");
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
      if (input === "/api/downloads") {
        return Promise.resolve(
          new Response(JSON.stringify({ items: [] }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
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
            published_at: "2026-07-20",
            estimated_size: 10_500_000,
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
    expect(screen.getByText(/20 jul 2026/i)).toBeVisible();
    expect(screen.getByText("Tamaño estimado: 10,5 MB")).toBeVisible();
    expect(screen.getByLabelText("Calidad")).toHaveValue("best");
    expect(screen.getByRole("option", { name: "Mejor disponible (720p)" })).toBeVisible();
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

    expect(
      screen.getByText("Pega una URL de YouTube o TikTok para analizarla."),
    ).toBeVisible();
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
        if (input === "/api/downloads") {
          return Promise.resolve(
            new Response(JSON.stringify({ items: [] }), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            }),
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
    expect(fetchMock).toHaveBeenCalledTimes(3);

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
            speed_bytes_per_second: 250000,
            eta_seconds: 65,
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
    expect(screen.getByText("1 MB de 1 MB")).toBeVisible();
    expect(screen.getByText("250 kB/s")).toBeVisible();
    expect(screen.getByText("1 min 5 s")).toBeVisible();
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
    expect(screen.getByLabelText("Progreso de Demo descargable")).toHaveValue(100);
  });

  it("shows indeterminate progress while processing without a percentage", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("video-downloader.usage-notice-version", "2026-07-20");
    vi.stubGlobal("fetch", createDownloadFlowMock());

    render(<App />);
    await inspectDemo(user);
    await user.click(screen.getByRole("button", { name: "Descargar" }));
    await screen.findByText("En cola");

    FakeEventSource.instances[0]?.emit("download.updated", {
      occurred_at: "2026-07-20T16:37:43Z",
      task: {
        ...downloadTask,
        status: "processing",
        queue_position: null,
        current_attempt: {
          ...downloadTask.current_attempt,
          status: "processing",
          progress: {
            percentage: null,
            downloaded_bytes: null,
            total_bytes: null,
            speed_bytes_per_second: null,
            eta_seconds: null,
          },
        },
      },
    });

    expect(await screen.findByText("Procesando archivo")).toBeVisible();
    expect(screen.getByLabelText("Procesando Demo descargable")).not.toHaveAttribute(
      "value",
    );
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
    expect(fetchMock).toHaveBeenCalledTimes(4);
  });

  it("cancels a queued download and hides the action in the terminal state", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("video-downloader.usage-notice-version", "2026-07-20");
    const cancelledTask = {
      ...downloadTask,
      status: "cancelled",
      queue_position: null,
      current_attempt: {
        ...downloadTask.current_attempt,
        status: "cancelled",
        finished_at: "2026-07-20T16:38:00Z",
      },
    };
    const fetchMock = createDownloadFlowMock(
      "video",
      undefined,
      Promise.resolve(
        new Response(JSON.stringify(cancelledTask), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await inspectDemo(user);
    await user.click(screen.getByRole("button", { name: "Descargar" }));
    await user.click(await screen.findByRole("button", { name: "Cancelar descarga" }));

    expect(await screen.findByText("Cancelada")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Cancelar descarga" })).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(`/api/downloads/${downloadTask.id}/cancel`, {
      method: "POST",
      headers: { Accept: "application/json" },
      signal: undefined,
    });
  });

  it("prevents duplicate cancellation requests while cancellation is pending", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("video-downloader.usage-notice-version", "2026-07-20");
    const pendingCancellation = new Promise<Response>(() => undefined);
    const fetchMock = createDownloadFlowMock("video", undefined, pendingCancellation);
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await inspectDemo(user);
    await user.click(screen.getByRole("button", { name: "Descargar" }));
    await user.click(await screen.findByRole("button", { name: "Cancelar descarga" }));

    const cancellingButton = screen.getByRole("button", { name: "Cancelando…" });
    expect(cancellingButton).toBeDisabled();
    await user.click(cancellingButton);
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        requestUrl(input).endsWith(`/${downloadTask.id}/cancel`),
      ),
    ).toHaveLength(1);
  });

  it("shows a cancellation error without losing the download card", async () => {
    const user = userEvent.setup();
    window.localStorage.setItem("video-downloader.usage-notice-version", "2026-07-20");
    const fetchMock = createDownloadFlowMock(
      "video",
      undefined,
      Promise.resolve(
        new Response(
          JSON.stringify({
            error: {
              code: "cancellation_not_allowed",
              message: "Esta descarga ya no puede cancelarse desde la cola.",
            },
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await inspectDemo(user);
    await user.click(screen.getByRole("button", { name: "Descargar" }));
    await user.click(await screen.findByRole("button", { name: "Cancelar descarga" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Esta descarga ya no puede cancelarse desde la cola.",
    );
    expect(screen.getAllByRole("heading", { name: "Demo descargable" })).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Cancelar descarga" })).toBeEnabled();
  });

  it("loads, deduplicates and orders persisted downloads newest first", async () => {
    const olderTask = {
      ...downloadTask,
      id: "older-task",
      title: "Descarga antigua",
      created_at: "2026-07-19T10:00:00Z",
    };
    const newerTask = {
      ...downloadTask,
      id: "newer-task",
      title: "Descarga reciente",
      created_at: "2026-07-20T10:00:00Z",
    };
    const updatedOlderTask = { ...olderTask, title: "Descarga antigua actualizada" };
    vi.stubGlobal("fetch", createHistoryMock([olderTask, newerTask, updatedOlderTask]));

    render(<App />);

    expect(await screen.findByText("2 descargas")).toBeVisible();
    expect(screen.queryByText("Descarga antigua")).toBeNull();
    expect(
      screen.getAllByRole("heading", { level: 3 }).map((heading) => heading.textContent),
    ).toEqual(["Descarga reciente", "Descarga antigua actualizada"]);
  });

  it("adds and updates history entries from backend events without duplicates", async () => {
    vi.stubGlobal("fetch", createHistoryMock([]));
    render(<App />);
    await screen.findByText(/Todavía no hay descargas/);

    FakeEventSource.instances[0]?.emit("download.created", {
      occurred_at: "2026-07-20T16:37:42Z",
      task: downloadTask,
    });
    expect(
      await screen.findByRole("heading", { name: "Demo descargable" }),
    ).toBeVisible();

    FakeEventSource.instances[0]?.emit("download.updated", {
      occurred_at: "2026-07-20T16:38:00Z",
      task: {
        ...downloadTask,
        status: "cancelled",
        queue_position: null,
        current_attempt: { ...downloadTask.current_attempt, status: "cancelled" },
      },
    });

    expect(await screen.findByText("Cancelada")).toBeVisible();
    expect(screen.getByText("1 descarga")).toBeVisible();
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(1);
  });

  it("shows a recoverable history error without hiding the rest of the app", async () => {
    vi.stubGlobal(
      "fetch",
      createHistoryMock([], {
        status: 500,
        body: {
          error: {
            code: "history_unavailable",
            message: "No se ha podido leer el historial local.",
          },
        },
      }),
    );

    render(<App />);

    expect(
      await screen.findByText("No se ha podido leer el historial local."),
    ).toBeVisible();
    expect(screen.getByLabelText("URL del video")).toBeEnabled();
  });

  it("retries a failed download in the same history entry", async () => {
    const user = userEvent.setup();
    const failedTask = createFailedDownloadTask();
    const retriedTask = {
      ...failedTask,
      status: "queued",
      queue_position: 1,
      attempts: [failedTask.current_attempt],
      current_attempt: {
        ...downloadTask.current_attempt,
        number: 2,
        created_at: "2026-07-20T17:00:00Z",
      },
    };
    const fetchMock = createHistoryMock([failedTask], undefined, (input) => {
      if (requestUrl(input).endsWith(`/${downloadTask.id}/retry`)) {
        return Promise.resolve(
          new Response(JSON.stringify(retriedTask), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return null;
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Reintentar" }));

    expect(await screen.findByText("En cola")).toBeVisible();
    expect(screen.queryByRole("button", { name: "Reintentar" })).toBeNull();
    expect(screen.getByRole("button", { name: "Cancelar descarga" })).toBeEnabled();
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(1);
    expect(fetchMock).toHaveBeenCalledWith(`/api/downloads/${downloadTask.id}/retry`, {
      method: "POST",
      headers: { Accept: "application/json" },
      signal: undefined,
    });
  });

  it("prevents duplicate retry requests while retry is pending", async () => {
    const user = userEvent.setup();
    const failedTask = createFailedDownloadTask();
    const pendingRetry = new Promise<Response>(() => undefined);
    const fetchMock = createHistoryMock([failedTask], undefined, (input) =>
      requestUrl(input).endsWith(`/${downloadTask.id}/retry`) ? pendingRetry : null,
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Reintentar" }));

    const retryingButton = screen.getByRole("button", { name: "Reintentando…" });
    expect(retryingButton).toBeDisabled();
    await user.click(retryingButton);
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        requestUrl(input).endsWith(`/${downloadTask.id}/retry`),
      ),
    ).toHaveLength(1);
  });

  it("shows retry errors on the affected card and enables retry again", async () => {
    const user = userEvent.setup();
    const failedTask = createFailedDownloadTask();
    const fetchMock = createHistoryMock([failedTask], undefined, (input) => {
      if (requestUrl(input).endsWith(`/${downloadTask.id}/retry`)) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              error: {
                code: "format_unavailable",
                message: "La calidad seleccionada ya no está disponible.",
              },
            }),
            { status: 409, headers: { "Content-Type": "application/json" } },
          ),
        );
      }
      return null;
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Reintentar" }));

    expect(
      await screen.findByText("La calidad seleccionada ya no está disponible."),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeEnabled();
    expect(screen.getByText("Fallida")).toBeVisible();
  });

  it("opens and reveals the file from a completed download card", async () => {
    const user = userEvent.setup();
    const completedTask = createCompletedDownloadTask();
    const fetchMock = createHistoryMock([completedTask], undefined, (input) => {
      if (requestUrl(input).endsWith(`/${downloadTask.id}/open`)) {
        return Promise.resolve(jsonResponse({ action: "opened" }));
      }
      if (requestUrl(input).endsWith(`/${downloadTask.id}/reveal`)) {
        return Promise.resolve(jsonResponse({ action: "revealed" }));
      }
      return null;
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Abrir archivo" }));
    await user.click(screen.getByRole("button", { name: "Mostrar en Finder" }));

    expect(fetchMock).toHaveBeenCalledWith(`/api/downloads/${downloadTask.id}/open`, {
      method: "POST",
      headers: { Accept: "application/json" },
      signal: undefined,
    });
    expect(fetchMock).toHaveBeenCalledWith(`/api/downloads/${downloadTask.id}/reveal`, {
      method: "POST",
      headers: { Accept: "application/json" },
      signal: undefined,
    });
    expect(screen.queryByRole("button", { name: "Reintentar" })).toBeNull();
  });

  it("blocks duplicate file actions and displays a card-specific error", async () => {
    const user = userEvent.setup();
    const completedTask = createCompletedDownloadTask();
    let resolveAction: ((response: Response) => void) | undefined;
    const pendingAction = new Promise<Response>((resolve) => {
      resolveAction = resolve;
    });
    const fetchMock = createHistoryMock([completedTask], undefined, (input) =>
      requestUrl(input).endsWith(`/${downloadTask.id}/open`) ? pendingAction : null,
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Abrir archivo" }));

    expect(screen.getByRole("button", { name: "Abriendo…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Mostrar en Finder" })).toBeDisabled();
    resolveAction?.(
      jsonResponse(
        {
          error: {
            code: "download_file_missing",
            message: "El archivo descargado ya no existe en la carpeta de destino.",
          },
        },
        404,
      ),
    );

    expect(
      await screen.findByText(
        "El archivo descargado ya no existe en la carpeta de destino.",
      ),
    ).toBeVisible();
    expect(screen.getByRole("button", { name: "Abrir archivo" })).toBeEnabled();
    expect(
      fetchMock.mock.calls.filter(([input]) =>
        requestUrl(input).endsWith(`/${downloadTask.id}/open`),
      ),
    ).toHaveLength(1);
  });

  it("confirms and removes a terminal history entry", async () => {
    const user = userEvent.setup();
    const completedTask = createCompletedDownloadTask();
    const fetchMock = createHistoryMock([completedTask], undefined, (input) =>
      requestUrl(input) === `/api/downloads/${downloadTask.id}`
        ? Promise.resolve(jsonResponse({ deleted: true }))
        : null,
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Eliminar del historial" }),
    );

    expect(
      screen.getByRole("dialog", { name: "¿Eliminar esta entrada?" }),
    ).toHaveTextContent("el archivo descargado no se borrará");
    await user.click(screen.getByRole("button", { name: "Conservar" }));
    expect(screen.getByRole("heading", { name: "Demo descargable" })).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Eliminar del historial" }));
    await user.click(screen.getByRole("button", { name: "Eliminar entrada" }));

    expect(await screen.findByText(/Todavía no hay descargas/)).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Demo descargable" })).toBeNull();
    expect(fetchMock).toHaveBeenCalledWith(`/api/downloads/${downloadTask.id}`, {
      method: "DELETE",
      headers: { Accept: "application/json" },
      signal: undefined,
    });
  });

  it("removes a history entry when another view publishes its deletion", async () => {
    const completedTask = createCompletedDownloadTask();
    vi.stubGlobal("fetch", createHistoryMock([completedTask]));
    render(<App />);
    await screen.findByRole("heading", { name: "Demo descargable" });

    FakeEventSource.instances[0]?.emit("download.deleted", {
      occurred_at: "2026-07-20T18:00:00Z",
      task: completedTask,
    });

    expect(await screen.findByText(/Todavía no hay descargas/)).toBeVisible();
  });

  it("keeps the card and shows an isolated deletion error", async () => {
    const user = userEvent.setup();
    const completedTask = createCompletedDownloadTask();
    const fetchMock = createHistoryMock([completedTask], undefined, (input) =>
      requestUrl(input) === `/api/downloads/${downloadTask.id}`
        ? Promise.resolve(
            jsonResponse(
              {
                error: {
                  code: "history_delete_failed",
                  message: "No se ha podido eliminar la entrada del historial.",
                },
              },
              500,
            ),
          )
        : null,
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<App />);
    await user.click(
      await screen.findByRole("button", { name: "Eliminar del historial" }),
    );
    await user.click(screen.getByRole("button", { name: "Eliminar entrada" }));

    expect(
      await screen.findByText("No se ha podido eliminar la entrada del historial."),
    ).toBeVisible();
    expect(screen.getByRole("heading", { name: "Demo descargable" })).toBeVisible();
    expect(screen.getByRole("button", { name: "Eliminar del historial" })).toBeEnabled();
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
  cancellationResponse?: Promise<Response>,
) {
  return vi.fn<typeof fetch>((input, init) => {
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
    if (input === "/api/downloads" && init?.method === "GET") {
      return Promise.resolve(
        new Response(JSON.stringify({ items: [] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    if (requestUrl(input).endsWith(`/${downloadTask.id}/cancel`)) {
      return (
        cancellationResponse ??
        Promise.resolve(
          new Response(JSON.stringify(downloadTask), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        )
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

function createHistoryMock(
  tasks: unknown[],
  error?: { status: number; body: unknown },
  handleAction?: (input: RequestInfo | URL) => Promise<Response> | null,
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
    if (input === "/api/downloads") {
      return Promise.resolve(
        new Response(JSON.stringify(error?.body ?? { items: tasks }), {
          status: error?.status ?? 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    const actionResponse = handleAction?.(input);
    if (actionResponse) return actionResponse;
    return Promise.reject(new Error(`Unexpected request: ${requestUrl(input)}`));
  });
}

function createFailedDownloadTask() {
  return {
    ...downloadTask,
    status: "failed",
    queue_position: null,
    current_attempt: {
      ...downloadTask.current_attempt,
      status: "failed",
      finished_at: "2026-07-20T16:50:00Z",
      failure: { code: "network_error", message: "La conexión se interrumpió." },
    },
  };
}

function createCompletedDownloadTask() {
  return {
    ...downloadTask,
    status: "completed",
    queue_position: null,
    current_attempt: {
      ...downloadTask.current_attempt,
      status: "completed",
      finished_at: "2026-07-20T16:50:00Z",
      result: {
        filename: "Demo descargable.mp4",
        extension: "mp4",
        size_bytes: 1_000_000,
        effective_quality: 720,
      },
    },
  };
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
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

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  return input instanceof URL ? input.href : input.url;
}
