// Waits for the backend (Tauri starts it; in a browser it is already running), then gives
// the rest of the app a typed API client. Until then it shows a start-up or error screen.
import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { errorMessage } from "@/i18n";
import { createApiClient, type ApiClient } from "@/lib/api/client";
import type { BackendConnection, BackendState, Platform } from "@/lib/platform";

export type FetchLike = (request: Request) => Promise<Response>;

interface Backend {
  client: ApiClient;
  connection: BackendConnection;
  fetch: FetchLike;
  platform: Platform;
}

const BackendContext = createContext<Backend | null>(null);

export function useBackend(): Backend {
  const backend = useContext(BackendContext);
  if (!backend) throw new Error("useBackend outside <BackendGate>");
  return backend;
}

export function useApi(): ApiClient {
  return useBackend().client;
}

export function BackendGate({
  platform,
  fetch,
  children,
}: {
  platform: Platform;
  fetch: FetchLike;
  children: ReactNode;
}) {
  const [state, setState] = useState<BackendState>({ status: "starting" });
  useEffect(() => platform.connectBackend(setState), [platform]);

  const connection = state.status === "ready" ? state.connection : null;
  const backend = useMemo<Backend | null>(
    () =>
      connection && {
        connection,
        fetch,
        platform,
        client: createApiClient({ baseUrl: connection.baseUrl, token: connection.token, fetch }),
      },
    [connection, fetch, platform],
  );

  if (state.status === "failed")
    return <StartupError code={state.error.code} params={state.error.params} />;
  if (!backend) return <Splash />;
  return <BackendContext.Provider value={backend}>{children}</BackendContext.Provider>;
}

function Splash() {
  const { t } = useTranslation();
  return (
    <div className="grid h-full place-items-center bg-canvas text-fg-muted" role="status">
      {t("backend.starting")}
    </div>
  );
}

function StartupError({
  code,
  params,
}: {
  code: string;
  params: Record<string, unknown> | undefined;
}) {
  const { t } = useTranslation();
  return (
    <div className="grid h-full place-items-center bg-canvas p-6">
      <div role="alert" className="max-w-md space-y-3 rounded-lg border border-line bg-raised p-6">
        <h1 className="text-h2 text-fg">{t("backend.failedTitle")}</h1>
        <p className="text-ui text-fg">{errorMessage(t, { code, params: params ?? {} })}</p>
        <Button
          onClick={() => {
            window.location.reload();
          }}
        >
          {t("backend.reload")}
        </Button>
      </div>
    </div>
  );
}
