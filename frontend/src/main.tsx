import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@/app/App";
import "@/styles/global.css";

const root = document.getElementById("root");

if (root === null) {
  throw new Error("No se ha encontrado el contenedor principal de la aplicación.");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
