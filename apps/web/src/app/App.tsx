// Composition root: i18n, server state (TanStack Query), backend connection, routing.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { I18nextProvider } from "react-i18next";
import { createHashRouter, Navigate, RouterProvider } from "react-router";

import { JobsPage } from "@/features/jobs/JobsPage";
import { SearchPage } from "@/features/search/SearchPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { createI18n } from "@/i18n";
import { detectPlatform, type Platform } from "@/lib/platform";
import { applyTheme, cachedLanguage, cachedTheme, resolveLanguage } from "@/lib/preferences";

import { BackendGate, type FetchLike } from "./backend";
import { ComingSoon } from "./ComingSoon";
import { AppShell } from "./layout/AppShell";

const sections = ["library", "screening", "reader", "notes", "matrix"] as const;

function createRouter() {
  // Hash routing: works the same from Tauri's asset protocol and any static server.
  return createHashRouter([
    {
      element: <AppShell />,
      children: [
        { index: true, element: <Navigate to="/library" replace /> },
        ...sections.map((section) => ({
          path: `/${section}`,
          element: <ComingSoon section={section} />,
        })),
        { path: "/search", element: <SearchPage /> },
        { path: "/jobs", element: <JobsPage /> },
        { path: "/settings/:section?", element: <SettingsPage /> },
        { path: "*", element: <Navigate to="/library" replace /> },
      ],
    },
  ]);
}

const defaultFetch: FetchLike = (request) => fetch(request);

export function App({
  platform = detectPlatform(),
  fetch = defaultFetch,
}: {
  platform?: Platform;
  fetch?: FetchLike;
}) {
  // Last choices from this device, so the first paint is right; the server's copy follows.
  const [i18n] = useState(() => {
    applyTheme(cachedTheme());
    return createI18n(resolveLanguage(cachedLanguage()));
  });
  const [queryClient] = useState(
    () => new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } }),
  );
  const [router] = useState(createRouter);

  return (
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <BackendGate platform={platform} fetch={fetch}>
          <RouterProvider router={router} />
        </BackendGate>
      </QueryClientProvider>
    </I18nextProvider>
  );
}
