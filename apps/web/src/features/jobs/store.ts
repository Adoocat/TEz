import { create } from "zustand";

import type { components } from "@/api/schema";

export type JobView = components["schemas"]["JobView"];

interface JobsState {
  /** The latest state of every job seen on the event stream, by id. */
  jobs: Record<string, JobView>;
  update: (job: JobView) => void;
}

export const useJobsStore = create<JobsState>()((set) => ({
  jobs: {},
  update: (job) => {
    set((state) => ({ jobs: { ...state.jobs, [job.id]: job } }));
  },
}));

export function countJobs(jobs: Record<string, JobView>): { active: number; failed: number } {
  let active = 0;
  let failed = 0;
  for (const job of Object.values(jobs)) {
    if (job.status === "queued" || job.status === "running") active += 1;
    else if (job.status === "failed") failed += 1;
  }
  return { active, failed };
}
