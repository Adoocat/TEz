// Composition root: i18n, server state (TanStack Query), backend connection, routing.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useState } from "react";
import { I18nextProvider } from "react-i18next";
import { createHashRouter, Navigate, RouterProvider } from "react-router";

import { ConflictsPage } from "@/features/dual-screening/ConflictsPage";
import { ExportPage } from "@/features/export/ExportPage";
import { JobsPage } from "@/features/jobs/JobsPage";
import { GalleryPage } from "@/features/gallery/GalleryPage";
import { LibraryPage } from "@/features/library/LibraryPage";
import { MatrixPage } from "@/features/matrix/MatrixPage";
import { ReaderPage } from "@/features/reader/ReaderPage";
import { ReviewPanel } from "@/features/reviews/ReviewPanel";
import { PrismaPage } from "@/features/prisma/PrismaPage";
import { QualityPage } from "@/features/quality/QualityPage";
import { ScreeningPage } from "@/features/screening/ScreeningPage";
import { SearchPage } from "@/features/search/SearchPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { createI18n } from "@/i18n";
import { detectPlatform, type Platform } from "@/lib/platform";
import { applyTheme, cachedLanguage, cachedTheme, resolveLanguage } from "@/lib/preferences";

import { BackendGate, type FetchLike } from "./backend";
import { AppShell } from "./layout/AppShell";

// The notes editor (CodeMirror) is not part of the start-up bundle.
const NotesPage = lazy(() =>
  import("@/features/notes/NotesPage").then((module) => ({ default: module.NotesPage })),
);

function createRouter() {
  // Hash routing: works the same from Tauri's asset protocol and any static server.
  return createHashRouter([
    {
      element: <AppShell />,
      children: [
        { index: true, element: <Navigate to="/library" replace /> },
        { path: "/matrix", element: <MatrixPage /> },
        { path: "/gallery", element: <GalleryPage /> },
        { path: "/review", element: <ReviewPanel /> },
        { path: "/screening", element: <ScreeningPage /> },
        { path: "/screening/conflicts", element: <ConflictsPage /> },
        { path: "/prisma", element: <PrismaPage /> },
        { path: "/quality", element: <QualityPage /> },
        { path: "/export", element: <ExportPage /> },
        { path: "/library", element: <LibraryPage /> },
        { path: "/reader/:attachmentId?", element: <ReaderPage /> },
        {
          path: "/notes/:noteId?",
          element: (
            <Suspense fallback={null}>
              <NotesPage />
            </Suspense>
          ),
        },
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
