import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import "@/index.css";
import App from "@/App";
import { AuthProvider } from "@/context/AuthContext";
import { OfflineProvider } from "@/context/OfflineContext";
import { Toaster } from "@/components/ui/sonner";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 10_000, refetchOnWindowFocus: false } },
});

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <QueryClientProvider client={queryClient}>
    <AuthProvider>
      <OfflineProvider>
        <App />
        <Toaster position="top-right" richColors />
      </OfflineProvider>
    </AuthProvider>
  </QueryClientProvider>
);

if ("serviceWorker" in navigator) {
  window.addEventListener("load", async () => {
    try {
      await navigator.serviceWorker.register("/sw.js");
    } catch {
      return; // SW optional
    }

    // Tell the worker exactly which files this page loaded so it can cache them.
    // Without this the first (uncontrolled) visit caches nothing and a reload
    // while offline lands on a blank page.
    const warm = () => {
      const ctrl = navigator.serviceWorker.controller;
      if (!ctrl) return;
      const origin = window.location.origin;
      const urls = performance
        .getEntriesByType("resource")
        .map((e) => e.name)
        .filter(
          (u) =>
            u.startsWith(origin) &&
            !u.includes("/api/") &&
            !u.includes("hot-update") &&
            !u.includes("sockjs") &&
            !u.includes("/ws")
        );
      ctrl.postMessage({ type: "WARM_CACHE", urls: [`${origin}/`, ...new Set(urls)] });
    };

    if (navigator.serviceWorker.controller) warm();
    else navigator.serviceWorker.addEventListener("controllerchange", warm);
  });
}
