import { useBackendHealth } from "@/hooks/useBackendHealth";

const statusCopy = {
  checking: "Comprobando backend",
  connected: "Backend conectado",
  disconnected: "Backend no disponible",
} as const;

export function App() {
  const backendStatus = useBackendHealth();

  return (
    <main className="app-shell">
      <section className="hero" aria-labelledby="app-title">
        <p className="eyebrow">Herramienta local</p>
        <h1 id="app-title">Video Downloader</h1>
        <p className="hero__description">
          Descarga únicamente contenido propio o que tengas derecho a guardar.
        </p>
        <div className="status" role="status" aria-live="polite">
          <span
            className={`status__dot status__dot--${backendStatus}`}
            aria-hidden="true"
          />
          {statusCopy[backendStatus]}
        </div>
      </section>
    </main>
  );
}
