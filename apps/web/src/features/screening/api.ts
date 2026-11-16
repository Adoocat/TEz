import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { reviewKeys } from "@/features/reviews/api";
import { unwrap } from "@/lib/api/query";

import { counts, withState, type QueueItem, type RecordState } from "./queue";

export type ScreeningStage = components["schemas"]["ScreeningStage"];
export type ScreeningQueue = components["schemas"]["ScreeningQueue"];
export type ScreeningRecord = components["schemas"]["ScreeningRecord"];
export type StageCriterion = components["schemas"]["StageCriterion"];
export type DecisionView = components["schemas"]["DecisionView"];
export type ChosenDecision = components["schemas"]["ChosenDecision"];

export const screeningKeys = {
  queue: (reviewId: string, stage: ScreeningStage) =>
    ["reviews", reviewId, "screening", stage, "queue"] as const,
  record: (reviewId: string, stage: ScreeningStage, paperId: string) =>
    ["reviews", reviewId, "screening", stage, "record", paperId] as const,
  criteria: (reviewId: string, stage: ScreeningStage) =>
    ["reviews", reviewId, "screening", stage, "criteria"] as const,
};

/** The whole queue, light rows only; filters and stepping work on it in the browser. */
export function useQueue(reviewId: string, stage: ScreeningStage) {
  const api = useApi();
  return useQuery({
    queryKey: screeningKeys.queue(reviewId, stage),
    staleTime: 0,
    queryFn: async () =>
      unwrap(
        await api.GET("/reviews/{review_id}/screening/{stage}", {
          params: { path: { review_id: reviewId, stage }, query: { filter: "all" } },
        }),
      ),
  });
}

function recordQuery(
  api: ReturnType<typeof useApi>,
  reviewId: string,
  stage: ScreeningStage,
  paperId: string,
) {
  return {
    queryKey: screeningKeys.record(reviewId, stage, paperId),
    queryFn: async () =>
      unwrap(
        await api.GET("/reviews/{review_id}/screening/{stage}/records/{paper_id}", {
          params: { path: { review_id: reviewId, stage, paper_id: paperId } },
        }),
      ),
  };
}

export function useRecord(reviewId: string, stage: ScreeningStage, paperId: string | null) {
  const api = useApi();
  return useQuery({
    ...recordQuery(api, reviewId, stage, paperId ?? ""),
    enabled: paperId !== null,
  });
}

/** Loads records ahead of time, so moving to them shows them at once. */
export function usePrefetchRecords(reviewId: string, stage: ScreeningStage) {
  const api = useApi();
  const queryClient = useQueryClient();
  return (paperIds: readonly (string | undefined)[]) => {
    for (const paperId of paperIds) {
      // A failed prefetch is retried when the record is shown, and reported there.
      if (paperId)
        queryClient.query(recordQuery(api, reviewId, stage, paperId)).catch(() => undefined);
    }
  };
}

export function useStageCriteria(reviewId: string, stage: ScreeningStage) {
  const api = useApi();
  return useQuery({
    queryKey: screeningKeys.criteria(reviewId, stage),
    queryFn: async () =>
      unwrap(
        await api.GET("/reviews/{review_id}/screening/{stage}/criteria", {
          params: { path: { review_id: reviewId, stage } },
        }),
      ),
  });
}

/** Puts a decision (or the state an undo restored) into the cached queue and record, so the
 * screen moves on without waiting for a refetch. */
function applyDecision(
  queryClient: QueryClient,
  reviewId: string,
  stage: ScreeningStage,
  decision: DecisionView,
) {
  const state: RecordState = decision.decision === "undecided" ? "undecided" : decision.decision;
  const change: Pick<QueueItem, "state" | "decision_id" | "criterion_id"> = {
    state,
    decision_id: decision.id,
    criterion_id: decision.criterion_id,
  };
  queryClient.setQueryData<ScreeningQueue>(screeningKeys.queue(reviewId, stage), (queue) => {
    if (!queue) return queue;
    const items = withState(queue.items, decision.paper_id, change);
    return { ...queue, items, counts: counts(items) };
  });
  queryClient.setQueryData<ScreeningRecord>(
    screeningKeys.record(reviewId, stage, decision.paper_id),
    (record) => (record ? { ...record, state, decision } : record),
  );
  // The review panel and the other stage's queue follow from this decision.
  void queryClient.invalidateQueries({ queryKey: reviewKeys.overview(reviewId) });
  const other: ScreeningStage = stage === "title_abstract" ? "full_text" : "title_abstract";
  void queryClient.invalidateQueries({ queryKey: screeningKeys.queue(reviewId, other) });
}

export interface DecideInput {
  paperId: string;
  decision: ChosenDecision;
  criterionId?: string | null;
  note?: string | null;
}

export function useDecide(reviewId: string, stage: ScreeningStage) {
  const api = useApi();
  const queryClient = useQueryClient();
  const key = screeningKeys.queue(reviewId, stage);
  return useMutation({
    mutationFn: async ({ paperId, decision, criterionId = null, note = null }: DecideInput) =>
      unwrap(
        await api.POST("/reviews/{review_id}/screening/{stage}/decisions", {
          params: { path: { review_id: reviewId, stage } },
          body: { paper_id: paperId, decision, criterion_id: criterionId, note },
        }),
      ),
    // The queue shows the decision at once, so a fast next key never lands on a record whose
    // decision is still on its way; a refused decision puts the queue back.
    onMutate: async ({ paperId, decision, criterionId = null }) => {
      await queryClient.cancelQueries({ queryKey: key });
      const before = queryClient.getQueryData<ScreeningQueue>(key);
      if (before) {
        const items = before.items.map((item) =>
          item.paper_id === paperId
            ? { ...item, state: decision, criterion_id: criterionId }
            : item,
        );
        queryClient.setQueryData<ScreeningQueue>(key, { ...before, items, counts: counts(items) });
      }
      return { before };
    },
    onError: (_error, input, context) => {
      if (!context?.before) return;
      const restored = context.before.items.find((item) => item.paper_id === input.paperId);
      if (!restored) return;
      queryClient.setQueryData<ScreeningQueue>(key, (queue) => {
        if (!queue) return queue;
        const items = withState(queue.items, input.paperId, restored);
        return { ...queue, items, counts: counts(items) };
      });
    },
    onSuccess: (decision) => {
      applyDecision(queryClient, reviewId, stage, decision);
    },
  });
}

export function useUndo(reviewId: string, stage: ScreeningStage) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (decisionId: string) =>
      unwrap(
        await api.POST("/reviews/{review_id}/screening/{stage}/undo", {
          params: { path: { review_id: reviewId, stage } },
          body: { decision_id: decisionId },
        }),
      ),
    onSuccess: (decision) => {
      applyDecision(queryClient, reviewId, stage, decision);
    },
  });
}
