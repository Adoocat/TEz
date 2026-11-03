import { CircleAlert, LoaderCircle } from "lucide-react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { countJobs, useJobsStore } from "@/features/jobs/store";
import { useLibraryInfo } from "@/features/settings/api";

export function StatusBar() {
  const { t } = useTranslation();
  const jobs = useJobsStore((state) => state.jobs);
  const { active, failed } = countJobs(jobs);
  const library = useLibraryInfo();

  return (
    <footer className="flex h-7 items-center gap-4 border-t border-line bg-surface px-3 text-meta text-fg-muted">
      <Link
        to="/jobs"
        className="flex items-center gap-1.5 hover:text-fg"
        data-testid="jobs-indicator"
      >
        {active > 0 ? (
          <>
            <LoaderCircle className="size-3.5 animate-spin text-primary" aria-hidden />
            {t("status.jobsRunning", { count: active })}
          </>
        ) : (
          t("status.jobsIdle")
        )}
        {failed > 0 && (
          <span className="flex items-center gap-1 text-danger">
            <CircleAlert className="size-3.5" aria-hidden />
            {t("status.jobsFailed", { count: failed })}
          </span>
        )}
      </Link>
      <div className="flex-1" />
      {library.data && <span>{t("status.library", { name: library.data.name })}</span>}
    </footer>
  );
}
