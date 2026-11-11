// Settings › Backup (design 5.11): back the library up now, see earlier backups, and how to
// restore one. A backup runs as a job, so its progress also shows in the status bar.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive } from "lucide-react";
import { useEffect } from "react";
import { useTranslation } from "react-i18next";

import { useApi } from "@/app/backend";
import { Button } from "@/components/ui/button";
import { useJobsStore } from "@/features/jobs/store";
import { unwrap } from "@/lib/api/query";

const backupsKey = ["backups"] as const;

function useBackups() {
  const api = useApi();
  return useQuery({
    queryKey: backupsKey,
    queryFn: async () => unwrap(await api.GET("/backups")),
  });
}

function useStartBackup() {
  const api = useApi();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/backups")),
  });
}

export function BackupSection() {
  const { t, i18n } = useTranslation();
  const backups = useBackups();
  const start = useStartBackup();
  const queryClient = useQueryClient();
  const jobId = start.data?.job_id;
  const job = useJobsStore((state) => (jobId ? state.jobs[jobId] : undefined));
  const running = start.isPending || job?.status === "queued" || job?.status === "running";

  useEffect(() => {
    if (job?.status === "done") void queryClient.invalidateQueries({ queryKey: backupsKey });
  }, [job?.status, queryClient]);

  const when = (value: string) =>
    new Date(value).toLocaleString(i18n.language, { dateStyle: "medium", timeStyle: "short" });
  const size = (bytes: number) =>
    t("settings.backup.megabytes", {
      size: (bytes / 1024 / 1024).toLocaleString(i18n.language, { maximumFractionDigits: 1 }),
    });

  return (
    <div className="space-y-4">
      <p className="text-ui text-fg-muted">{t("settings.backup.about")}</p>
      <div className="flex items-center gap-3">
        <Button
          variant="primary"
          disabled={running}
          onClick={() => {
            start.mutate();
          }}
        >
          <Archive aria-hidden />
          {running ? t("settings.backup.running") : t("settings.backup.now")}
        </Button>
        <span aria-live="polite" className="text-meta text-fg-muted">
          {job?.status === "running" && job.progress !== null
            ? t("settings.backup.progress", { percent: Math.round(job.progress * 100) })
            : job?.status === "done"
              ? t("settings.backup.done")
              : job?.status === "failed"
                ? t("settings.backup.failed")
                : ""}
        </span>
      </div>
      {backups.data?.length === 0 ? (
        <p className="text-meta text-fg-muted">{t("settings.backup.none")}</p>
      ) : (
        <table className="w-full text-left text-ui">
          <thead className="text-meta text-fg-muted">
            <tr className="border-b border-line">
              <th className="py-1 pr-3 font-normal">{t("settings.backup.date")}</th>
              <th className="pr-3 font-normal">{t("settings.backup.contents")}</th>
              <th className="pr-3 text-right font-normal">{t("settings.backup.size")}</th>
              <th className="font-normal">{t("settings.backup.file")}</th>
            </tr>
          </thead>
          <tbody>
            {backups.data?.map((backup) => (
              <tr key={backup.file_name} className="border-b border-line">
                <td className="py-1 pr-3 whitespace-nowrap">{when(backup.created_at)}</td>
                <td className="pr-3 text-meta text-fg-muted">
                  {backup.papers !== null && backup.attachments !== null
                    ? t("settings.backup.counts", {
                        papers: backup.papers,
                        files: backup.attachments,
                      })
                    : t("settings.backup.unreadable")}
                </td>
                <td className="pr-3 text-right tabular-nums">{size(backup.size)}</td>
                <td className="font-mono text-meta break-all">{backup.file_name}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="space-y-1 rounded-md border border-line p-3">
        <h3 className="text-ui font-medium">{t("settings.backup.restoreTitle")}</h3>
        <p className="text-meta text-fg-muted">{t("settings.backup.restoreText")}</p>
        <code className="block rounded-xs bg-surface p-2 font-mono text-code">
          tez-backend restore &lt;TEz-backup-….zip&gt; &lt;{t("settings.backup.newFolder")}&gt;
        </code>
      </div>
    </div>
  );
}
