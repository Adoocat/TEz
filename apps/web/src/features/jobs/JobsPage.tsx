import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { useApi } from "@/app/backend";
import { unwrap } from "@/lib/api/query";

export function JobsPage() {
  const { t } = useTranslation();
  const api = useApi();
  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: async () => unwrap(await api.GET("/jobs")),
  });

  return (
    <div className="space-y-4 p-6">
      <h1 className="text-h1">{t("jobs.title")}</h1>
      {jobs.data?.length === 0 && <p className="text-fg-muted">{t("jobs.empty")}</p>}
      {jobs.data && jobs.data.length > 0 && (
        <table className="w-full text-left text-ui">
          <thead className="text-meta text-fg-muted">
            <tr className="border-b border-line">
              <th className="h-row font-normal">{t("jobs.type")}</th>
              <th className="font-normal">{t("jobs.state")}</th>
              <th className="font-normal">{t("jobs.progress")}</th>
              <th className="font-normal">{t("jobs.attempts")}</th>
            </tr>
          </thead>
          <tbody>
            {jobs.data.map((job) => (
              <tr key={job.id} className="h-row border-b border-line">
                <td>{t(`jobs.types.${job.type}`, { defaultValue: job.type })}</td>
                <td>{t(`jobs.statuses.${job.status}`)}</td>
                <td>
                  {job.progress === null ? "—" : `${String(Math.round(job.progress * 100))}%`}
                </td>
                <td>
                  {job.attempts}/{job.max_attempts}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
