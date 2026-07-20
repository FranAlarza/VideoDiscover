import { getDownloads, isDownloadTask, type DownloadTask } from "@/api/downloads";

export type DownloadEventConnectionStatus = "connecting" | "connected" | "disconnected";

export interface DownloadEventClient {
  close: () => void;
}

interface SubscribeOptions {
  onTask: (task: DownloadTask) => void;
  onSnapshot: (tasks: DownloadTask[]) => void;
  onConnectionStatus: (status: DownloadEventConnectionStatus) => void;
  EventSourceClass?: typeof EventSource;
}

export function subscribeToDownloadEvents({
  onTask,
  onSnapshot,
  onConnectionStatus,
  EventSourceClass = EventSource,
}: SubscribeOptions): DownloadEventClient {
  onConnectionStatus("connecting");
  const source = new EventSourceClass("/api/events");
  let closed = false;

  source.onopen = () => {
    if (!closed) {
      onConnectionStatus("connected");
    }
  };

  source.onerror = () => {
    if (!closed) {
      onConnectionStatus("disconnected");
    }
  };

  source.addEventListener("download.updated", (event) => {
    const task = parseTaskEvent(event);
    if (task) {
      onTask(task);
    }
  });

  source.addEventListener("download.created", (event) => {
    const task = parseTaskEvent(event);
    if (task) {
      onTask(task);
    }
  });

  source.addEventListener("downloads.snapshot", (event) => {
    const tasks = parseSnapshotEvent(event);
    if (tasks) {
      onSnapshot(tasks);
    }
  });

  source.addEventListener("downloads.resync", () => {
    void getDownloads()
      .then(onSnapshot)
      .catch(() => {
        if (!closed) {
          onConnectionStatus("disconnected");
        }
      });
  });

  return {
    close() {
      closed = true;
      source.close();
    },
  };
}

function parseTaskEvent(event: MessageEvent): DownloadTask | null {
  const payload = parseEventJson(event);
  if (!isRecord(payload) || !isDownloadTask(payload.task)) {
    return null;
  }
  return payload.task;
}

function parseSnapshotEvent(event: MessageEvent): DownloadTask[] | null {
  const payload = parseEventJson(event);
  if (
    !isRecord(payload) ||
    !Array.isArray(payload.items) ||
    !payload.items.every(isDownloadTask)
  ) {
    return null;
  }
  return payload.items;
}

function parseEventJson(event: MessageEvent): unknown {
  return typeof event.data === "string" ? parseJson(event.data) : null;
}

function parseJson(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
