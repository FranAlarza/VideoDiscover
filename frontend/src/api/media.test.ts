import { describe, expect, it, vi } from "vitest";

import { inspectMedia, MediaApiError } from "@/api/media";

describe("inspectMedia", () => {
  it("posts the URL to the inspection endpoint", async () => {
    const inspection = {
      platform: "youtube",
      media_id: "abc123",
      title: "Demo video",
      author: "Fran",
      duration_seconds: 95,
      thumbnail_url: "https://example.com/thumb.jpg",
      published_at: null,
      estimated_size: null,
      video_qualities: [720, 360],
      audio_available: true,
      is_live: false,
    };
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(inspection), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(inspectMedia("https://youtu.be/abc123")).resolves.toEqual(inspection);
    expect(fetchMock).toHaveBeenCalledWith("/api/media/inspect", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ url: "https://youtu.be/abc123" }),
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
              code: "unsupported_platform",
              message: "Solo se admiten URLs de YouTube y TikTok.",
            },
          }),
          { status: 400, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(inspectMedia("https://example.com/video")).rejects.toMatchObject({
      name: "MediaApiError",
      code: "unsupported_platform",
      message: "Solo se admiten URLs de YouTube y TikTok.",
      status: 400,
    } satisfies Partial<MediaApiError>);
  });
});
