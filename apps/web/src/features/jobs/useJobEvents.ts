// Follows GET /jobs/events (SSE) for the whole app and keeps the jobs store current.
// Reconnects after a drop, resuming with Last-Event-ID so no update is lost.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";

import { useBackend } from "@/app/backend";
import { parseSse } from "@/lib/sse";

import { useJobsStore, type JobView } from "./store";

const RECONNECT_MS = 2000;

export function useJobEvents(): void {
  const { connection, fetch } = useBackend();
  const update = useJobsStore((state) => state.update);
  const queryClient = useQueryClient();

  useEffect(() => {
    const abort = new AbortController();
    let lastEventId: string | undefined;

    async function follow(): Promise<void> {
      while (!abort.signal.aborted) {
        try {
          const headers = new Headers({ Accept: "text/event-stream" });
          if (connection.token) headers.set("Authorization", `Bearer ${connection.token}`);
          if (lastEventId) headers.set("Last-Event-ID", lastEventId);
          const response = await fetch(
            new Request(`${connection.baseUrl}/jobs/events`, { headers, signal: abort.signal }),
          );
          if (response.ok && response.body) {
            for await (const message of parseSse(response.body)) {
              if (message.event !== "job") continue;
              lastEventId = message.id ?? lastEventId;
              update(JSON.parse(message.data) as JobView);
              void queryClient.invalidateQueries({ queryKey: ["jobs"] });
            }
          }
        } catch {
          // Aborted (unmount), or the backend is restarting: the loop condition decides.
        }
        await new Promise((resolve) => setTimeout(resolve, RECONNECT_MS));
      }
    }

    void follow();
    return () => {
      abort.abort();
    };
  }, [connection, fetch, update, queryClient]);
}
