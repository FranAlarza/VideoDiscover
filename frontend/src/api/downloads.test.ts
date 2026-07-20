import { describe, expect, it, vi } from "vitest";

import {
  cancelDownload,
  createDownload,
  DownloadApiError,
  type DownloadCreateRequest,
} from "@/api/downloads";

const task = {
  id: "ad73f0bf-b078-4d21-a4b1-a7517679aec5",
  platform: "youtube",
  media_id: "abc123",
  title: "Demo",
  selection: { output_type: "video", video_quality: 720, audio_bitrate: null },
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

describe("createDownload", () => {
  it("posts the exact selection to the downloads endpoint", async () => {
    const request: DownloadCreateRequest = {
      url: "https://youtu.be/abc123",
      output_type: "video",
      video_quality: 720,
      audio_bitrate: null,
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(task), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(createDownload(request)).resolves.toMatchObject({ id: task.id });
    expect(fetchMock).toHaveBeenCalledWith("/api/downloads", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(request),
      signal: undefined,
    });
  });

  it("throws stable backend errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "format_unavailable",
              message: "La calidad seleccionada ya no está disponible.",
            },
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(
      createDownload({
        url: "https://youtu.be/abc123",
        output_type: "video",
        video_quality: 720,
        audio_bitrate: null,
      }),
    ).rejects.toMatchObject({
      name: "DownloadApiError",
      code: "format_unavailable",
      status: 409,
    } satisfies Partial<DownloadApiError>);
  });
});

describe("cancelDownload", () => {
  it("posts to the task cancellation endpoint", async () => {
    const cancelledTask = {
      ...task,
      status: "cancelled",
      queue_position: null,
      current_attempt: { ...task.current_attempt, status: "cancelled" },
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(cancelledTask), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(cancelDownload(task.id)).resolves.toMatchObject({
      id: task.id,
      status: "cancelled",
    });
    expect(fetchMock).toHaveBeenCalledWith(`/api/downloads/${task.id}/cancel`, {
      method: "POST",
      headers: { Accept: "application/json" },
      signal: undefined,
    });
  });

  it("preserves stable cancellation errors", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
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

    await expect(cancelDownload(task.id)).rejects.toMatchObject({
      name: "DownloadApiError",
      code: "cancellation_not_allowed",
      status: 409,
    } satisfies Partial<DownloadApiError>);
  });
});
