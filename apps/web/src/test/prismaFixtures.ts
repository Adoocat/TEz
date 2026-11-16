// A review's PRISMA counts that keep every invariant of Task 34, for the diagram's tests.
import { prismaBranch, prismaCounts } from "./fakeBackend";

export const sampleCounts = prismaCounts({
  review_id: "review-1",
  databases: {
    ...prismaBranch({
      identified: 1425,
      duplicates: 294,
      screened: 1131,
      excluded: 1000,
      awaiting_screening: 31,
      sought: 100,
      not_retrieved: 7,
      assessed: 90,
      awaiting_full_text: 3,
      excluded_reports: [
        { criterion_id: "c1", code: "E1", text: "Not peer reviewed", count: 50 },
        { criterion_id: "c2", code: "E2", text: "No <empirical> data & no code", count: 22 },
      ],
      included: 18,
    }),
    sources: [
      { source: "Scopus", runs: 2, identified: 842 },
      { source: "PubMed", runs: 1, identified: 583 },
    ],
  },
  other_methods: {
    ...prismaBranch({
      identified: 45,
      duplicates: 6,
      screened: 39,
      excluded: 30,
      sought: 9,
      not_retrieved: 1,
      assessed: 8,
      excluded_reports: [{ criterion_id: "c1", code: "E1", text: "Not peer reviewed", count: 3 }],
      included: 5,
    }),
    methods: [
      { method: "citation_backward", round: 1, identified: 40 },
      { method: "thesis", round: null, identified: 5 },
    ],
  },
  included: 23,
});
