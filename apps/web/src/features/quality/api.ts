// Quality assessment (Task 38): the optional stage, its question set and the answers.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap, unwrapEmpty } from "@/lib/api/query";

export type QualityView = components["schemas"]["QualityView"];
export type QuestionView = components["schemas"]["QuestionView"];
export type QuestionCreate = components["schemas"]["QuestionCreate"];
export type QuestionPatch = components["schemas"]["QuestionPatch"];
export type ScaleOption = components["schemas"]["ScaleOption"];
export type QualityCatalog = components["schemas"]["QualityCatalog"];
export type TemplateView = components["schemas"]["TemplateView"];
export type ScalePresetView = components["schemas"]["ScalePresetView"];
export type PaperQualityRow = components["schemas"]["PaperQualityRow"];
export type PaperAssessment = components["schemas"]["PaperAssessment"];
export type QualitySummary = components["schemas"]["QualitySummary"];
export type Language = components["schemas"]["TemplateApply"]["language"];

export const qualityKeys = {
  catalog: ["quality-catalog"] as const,
  all: (reviewId: string) => ["reviews", reviewId, "quality"] as const,
  set: (reviewId: string) => ["reviews", reviewId, "quality", "set"] as const,
  summary: (reviewId: string) => ["reviews", reviewId, "quality", "summary"] as const,
  papers: (reviewId: string) => ["reviews", reviewId, "quality", "papers"] as const,
  paper: (reviewId: string, paperId: string) =>
    ["reviews", reviewId, "quality", "paper", paperId] as const,
};

const path = (reviewId: string) => ({ params: { path: { review_id: reviewId } } });

export function useQualityCatalog() {
  const api = useApi();
  return useQuery({
    queryKey: qualityKeys.catalog,
    staleTime: Infinity,
    queryFn: async () => unwrap(await api.GET("/quality/catalog")),
  });
}

export function useQuality(reviewId: string) {
  const api = useApi();
  return useQuery({
    queryKey: qualityKeys.set(reviewId),
    queryFn: async () => unwrap(await api.GET("/reviews/{review_id}/quality", path(reviewId))),
  });
}

/** The stage's derived numbers; the review panel hides the stage when it is off. */
export function useQualitySummary(reviewId: string) {
  const api = useApi();
  return useQuery({
    queryKey: qualityKeys.summary(reviewId),
    staleTime: 0,
    queryFn: async () =>
      unwrap(await api.GET("/reviews/{review_id}/quality/summary", path(reviewId))),
  });
}

/** Every quality mutation can change the summary and the paper rows: refetch them all. */
function useInvalidate(reviewId: string) {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: qualityKeys.all(reviewId) });
}

export function useSetQualityEnabled(reviewId: string) {
  const api = useApi();
  const invalidate = useInvalidate(reviewId);
  return useMutation({
    mutationFn: async (enabled: boolean) =>
      unwrap(
        await api.PUT("/reviews/{review_id}/quality/setting", {
          ...path(reviewId),
          body: { enabled },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useAddQuestions(reviewId: string) {
  const api = useApi();
  const invalidate = useInvalidate(reviewId);
  return useMutation({
    mutationFn: async (questions: QuestionCreate[]) =>
      unwrap(
        await api.POST("/reviews/{review_id}/quality/questions", {
          ...path(reviewId),
          body: { questions },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useApplyTemplate(reviewId: string) {
  const api = useApi();
  const invalidate = useInvalidate(reviewId);
  return useMutation({
    mutationFn: async ({ template, language }: { template: string; language: Language }) =>
      unwrap(
        await api.POST("/reviews/{review_id}/quality/templates/{template_key}", {
          params: { path: { review_id: reviewId, template_key: template } },
          body: { language },
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useUpdateQuestion(reviewId: string) {
  const api = useApi();
  const invalidate = useInvalidate(reviewId);
  return useMutation({
    mutationFn: async ({ id, patch }: { id: string; patch: QuestionPatch }) =>
      unwrap(
        await api.PATCH("/reviews/{review_id}/quality/questions/{question_id}", {
          params: { path: { review_id: reviewId, question_id: id } },
          body: patch,
        }),
      ),
    onSuccess: invalidate,
  });
}

export function useDeleteQuestion(reviewId: string) {
  const api = useApi();
  const invalidate = useInvalidate(reviewId);
  return useMutation({
    mutationFn: async (id: string) => {
      unwrapEmpty(
        await api.DELETE("/reviews/{review_id}/quality/questions/{question_id}", {
          params: { path: { review_id: reviewId, question_id: id } },
        }),
      );
    },
    onSuccess: invalidate,
  });
}

export function useReorderQuestions(reviewId: string) {
  const api = useApi();
  const invalidate = useInvalidate(reviewId);
  return useMutation({
    mutationFn: async (questionIds: string[]) =>
      unwrap(
        await api.PUT("/reviews/{review_id}/quality/order", {
          ...path(reviewId),
          body: { question_ids: questionIds },
        }),
      ),
    onSuccess: invalidate,
  });
}

/** Papers included at full text, with derived progress and totals. */
export function useQualityPapers(reviewId: string) {
  const api = useApi();
  return useQuery({
    queryKey: qualityKeys.papers(reviewId),
    staleTime: 0,
    queryFn: async () =>
      unwrap(await api.GET("/reviews/{review_id}/quality/papers", path(reviewId))),
  });
}

export function usePaperAssessment(reviewId: string, paperId: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: qualityKeys.paper(reviewId, paperId ?? ""),
    enabled: paperId !== null,
    queryFn: async () =>
      unwrap(
        await api.GET("/reviews/{review_id}/quality/papers/{paper_id}", {
          params: { path: { review_id: reviewId, paper_id: paperId ?? "" } },
        }),
      ),
  });
}

export function useSaveAnswer(reviewId: string, paperId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: { questionId: string; answer: string | null; note: string | null }) =>
      unwrap(
        await api.PUT("/reviews/{review_id}/quality/papers/{paper_id}/answers/{question_id}", {
          params: {
            path: { review_id: reviewId, paper_id: paperId, question_id: input.questionId },
          },
          body: { answer: input.answer, note: input.note },
        }),
      ),
    onSuccess: async (saved) => {
      queryClient.setQueryData(qualityKeys.paper(reviewId, paperId), saved);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: qualityKeys.papers(reviewId) }),
        queryClient.invalidateQueries({ queryKey: qualityKeys.summary(reviewId) }),
      ]);
    },
  });
}

/** "6 / 9", or null when the set has no scored options. */
export function formatScore(row: PaperQualityRow, number: (value: number) => string) {
  if (row.score === null || row.max_score === null) return null;
  return `${number(row.score)} / ${number(row.max_score)}`;
}
