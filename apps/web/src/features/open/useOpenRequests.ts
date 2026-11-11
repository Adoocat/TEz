// What happens when TEz is asked to open something from outside (design 4.6): the same
// response whether the window was already open or has just started (Task 22).
//
// - a PDF goes to the inbox (or is found already there) and opens in the reader;
// - several PDFs, or a folder of them, go to the inbox with one summary notice;
// - a .bib or .ris file opens the import dialog;
// - a `tez://` link only navigates; a TEz library folder cannot be switched to yet.
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useEffectEvent } from "react";
import { useNavigate } from "react-router";

import { useBackend } from "@/app/backend";
import { useUploadStore } from "@/features/files/store";
import { useLibraryView } from "@/features/library/store";
import { unwrap } from "@/lib/api/query";
import type { OpenRequest } from "@/lib/platform";

import { useOpenStore } from "./store";

/** Where a `tez://` link leads, as an app route; null for a link we do not know. */
export function routeOf(url: string): { route: string; paperId?: string } | null {
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    return null;
  }
  if (parsed.protocol !== "tez:") return null;
  const id = decodeURIComponent(parsed.pathname.replace(/^\/+/, "").split("/")[0] ?? "");
  const page = Number.parseInt(parsed.searchParams.get("page") ?? "", 10);
  switch (parsed.hostname) {
    case "reader":
      if (!id) return { route: "/reader" };
      return {
        route: `/reader/${encodeURIComponent(id)}${Number.isNaN(page) ? "" : `?page=${String(page)}`}`,
      };
    case "paper":
      return id ? { route: "/library", paperId: id } : null;
    case "library":
    case "search":
    case "jobs":
      return { route: `/${parsed.hostname}` };
    default:
      return null;
  }
}

function fileName(path: string): string {
  return path.split(/[\\/]/).pop() ?? path;
}

export function useOpenRequests() {
  const { platform, client } = useBackend();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const notices = useUploadStore();
  const selectPaper = useLibraryView((state) => state.selectPaper);
  const setImportPath = useOpenStore((state) => state.setImportPath);
  async function fromPaths(paths: string[]) {
    const results = unwrap(await client.POST("/pdfs/from-paths", { body: { paths } }));
    void queryClient.invalidateQueries({ queryKey: ["library"] });
    return results;
  }

  async function addOne(path: string) {
    const id = notices.start(fileName(path));
    try {
      const [result] = await fromPaths([path]);
      if (result?.added) {
        notices.update(id, { state: result.added.status });
        void navigate(`/reader/${result.added.attachment_id}`);
      } else {
        notices.update(id, {
          state: "failed",
          errorCode: result?.error?.code ?? "unknown",
          errorParams: result?.error?.params ?? {},
        });
      }
    } catch {
      notices.update(id, { state: "failed", errorCode: "unknown" });
    }
  }

  async function addMany(folder: string | null, paths: string[], truncated: boolean) {
    const id = notices.start(folder ? fileName(folder) : `${String(paths.length)} PDF`);
    try {
      const results = await fromPaths(paths);
      const added = results.filter((r) => r.added?.status === "added").length;
      const duplicates = results.filter((r) => r.added?.status === "duplicate").length;
      notices.update(id, {
        state: "info",
        messageKey: truncated ? "open.addedSomeTruncated" : "open.addedSome",
        messageParams: { added, duplicates, failed: results.length - added - duplicates },
      });
    } catch {
      notices.update(id, { state: "failed", errorCode: "unknown" });
    }
  }

  // An effect event: the subscription stays put while the handler sees fresh state.
  const onRequests = useEffectEvent((requests: OpenRequest[]) => {
    void (async () => {
      const pdfs = requests.flatMap((r) => (r.kind === "pdf" ? [r.path] : []));
      for (const request of requests) {
        switch (request.kind) {
          case "focus":
          case "pdf":
            break;
          case "import":
            setImportPath(request.path);
            void navigate("/search");
            break;
          case "link": {
            const target = routeOf(request.url);
            if (target === null) {
              notices.inform(request.url, "open.unknownLink");
              break;
            }
            if (target.paperId) selectPaper(target.paperId);
            void navigate(target.route);
            break;
          }
          case "folder":
            if (request.is_library) {
              notices.inform(fileName(request.path), "open.isLibrary");
            } else if (request.pdfs.length === 0) {
              notices.inform(fileName(request.path), "open.noPdfs");
            } else {
              await addMany(request.path, request.pdfs, request.truncated);
            }
            break;
          case "missing":
            notices.inform(fileName(request.path), "open.missing");
            break;
          case "unsupported":
            notices.inform(fileName(request.path), "open.unsupported");
            break;
        }
      }
      if (pdfs.length === 1) await addOne(pdfs[0] ?? "");
      else if (pdfs.length > 1) await addMany(null, pdfs, false);
    })();
  });

  useEffect(
    () =>
      platform.onOpenRequests((requests) => {
        onRequests(requests);
      }),
    [platform],
  );
}
