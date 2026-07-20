import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
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
});
