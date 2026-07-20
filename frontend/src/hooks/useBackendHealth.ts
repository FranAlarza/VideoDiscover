import { useEffect, useState } from "react";

import { checkBackendHealth, type HealthStatus } from "@/api/health";

export function useBackendHealth(): HealthStatus {
  const [status, setStatus] = useState<HealthStatus>("checking");

  useEffect(() => {
    const controller = new AbortController();

    void checkBackendHealth(controller.signal)
      .then((isConnected) => {
        setStatus(isConnected ? "connected" : "disconnected");
      })
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          setStatus("disconnected");
        }
      });

    return () => {
      controller.abort();
    };
  }, []);

  return status;
}
