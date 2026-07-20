import { render, screen } from "@testing-library/react";
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
});
