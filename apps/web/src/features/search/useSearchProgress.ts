// Follows GET /searches/{id}/events (SSE) while a search runs. Results refresh each time a
// source finishes, so they appear as they arrive rather than only at the end.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { useBackend } from "@/app/backend";
import { parseSse } from "@/lib/sse";

import { searchKeys, type SourceProgress } from "./api";

const FINISHED_STATES: readonly SourceProgress["state"][] = ["done", "partial", "failed"];

export interface SearchProgress {
  sources: Record<string, SourceProgress>;
  running: boolean;
}

interface Followed {
  searchId: string | null;
  sources: Record<string, SourceProgress>;
  ended: boolean;
}

export function useSearchProgress(searchId: string | null): SearchProgress {
  const { connection, fetch } = useBackend();
  const queryClient = useQueryClient();
  // Tagged with its search, so progress of the previous search is never shown for a new one.
  const [followed, setFollowed] = useState<Followed>({ searchId, sources: {}, ended: false });

  useEffect(() => {
    if (searchId === null) return;
    const abort = new AbortController();

    const refresh = () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: searchKeys.results(searchId) }),
        queryClient.invalidateQueries({ queryKey: searchKeys.overview(searchId) }),
      ]);

    async function follow(): Promise<void> {
      const headers = new Headers({ Accept: "text/event-stream" });
      if (connection.token) headers.set("Authorization", `Bearer ${connection.token}`);
      const response = await fetch(
        new Request(`${connection.baseUrl}/searches/${searchId ?? ""}/events`, {
          headers,
          signal: abort.signal,
        }),
      );
      // 404: this search is not running in this process, so what it found is all on record.
      if (response.ok && response.body) {
        for await (const message of parseSse(response.body)) {
          if (message.event !== "source") continue;
          const update = JSON.parse(message.data) as SourceProgress;
          setFollowed((current) => ({
            searchId,
            ended: false,
            sources: {
              ...(current.searchId === searchId ? current.sources : {}),
              [update.source]: update,
            },
          }));
          if (FINISHED_STATES.includes(update.state)) void refresh();
        }
      }
    }

    follow()
      .catch(() => undefined) // Aborted, or the backend went away: what is on record stays.
      .finally(() => {
        if (abort.signal.aborted) return;
        setFollowed((current) => ({
          searchId,
          ended: true,
          sources: current.searchId === searchId ? current.sources : {},
        }));
        void refresh();
        void queryClient.invalidateQueries({ queryKey: ["searches", "history"] });
      });
    return () => {
      abort.abort();
    };
  }, [searchId, connection, fetch, queryClient]);

  if (searchId === null) return { sources: {}, running: false };
  if (followed.searchId !== searchId) return { sources: {}, running: true };
  return { sources: followed.sources, running: !followed.ended };
}
