import { afterEach, describe, expect, it, vi } from "vitest";

import {
  chooseDownloadDirectory,
  getLocalSettings,
  SettingsApiError,
} from "@/api/settings";

describe("settings API", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("loads the current download directory", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ download_output_root: "/Users/demo/Downloads" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(getLocalSettings()).resolves.toEqual({
      download_output_root: "/Users/demo/Downloads",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/settings",
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("opens the native chooser and returns the updated directory", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ download_output_root: "/Users/demo/Videos" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(chooseDownloadDirectory()).resolves.toEqual({
      download_output_root: "/Users/demo/Videos",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/settings/download-directory/choose",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("preserves a stable backend error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(
          JSON.stringify({
            error: {
              code: "directory_selection_cancelled",
              message: "No se ha cambiado la carpeta de descargas.",
            },
          }),
          { status: 409, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );

    await expect(chooseDownloadDirectory()).rejects.toMatchObject({
      code: "directory_selection_cancelled",
      status: 409,
    } satisfies Partial<SettingsApiError>);
  });
});
