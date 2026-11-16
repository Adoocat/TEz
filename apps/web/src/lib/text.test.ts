import { describe, expect, it } from "vitest";

import cases from "../../../../backend/tests/fixtures/text/fold_cases.json";

import { fold, highlight } from "./text";

describe("fold", () => {
  it.each(cases as [string, string][])("folds %s like the backend", (text, expected) => {
    expect(fold(text)).toBe(expected);
  });
});

describe("highlight", () => {
  const terms = [
    { term: "kod inceleme", value: "I1" },
    { term: "LLM", value: "I2" },
    { term: "ışık", value: "E1" },
  ];

  it("finds terms whatever the case and Turkish letters", () => {
    const segments = highlight("LLM ile KOD İNCELEMESİ ve IŞIK", terms);

    expect(segments).toEqual([
      { text: "LLM", match: "I2" },
      { text: " ile " },
      { text: "KOD İNCELEME", match: "I1" },
      { text: "Sİ ve " },
      { text: "IŞIK", match: "E1" },
    ]);
  });

  it("matches only from the start of a word", () => {
    expect(highlight("unllm llms", [{ term: "llm", value: 1 }])).toEqual([
      { text: "unllm " },
      { text: "llm", match: 1 },
      { text: "s" },
    ]);
  });

  it("lets the longer of two overlapping terms win", () => {
    const segments = highlight("code review tools", [
      { term: "review", value: "short" },
      { term: "code review", value: "long" },
    ]);
    expect(segments[0]).toEqual({ text: "code review", match: "long" });
  });

  it("keeps the text intact when nothing matches", () => {
    expect(highlight("Café résumé", [])).toEqual([{ text: "Café résumé" }]);
  });
});
