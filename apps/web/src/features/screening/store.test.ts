// The session counter counts the decisions this session still stands by.
import { beforeEach, describe, expect, it } from "vitest";

import { useScreeningSession } from "./store";

beforeEach(() => {
  useScreeningSession.setState({ decided: 0, done: [], pendingNotes: {} });
});

describe("the screening session", () => {
  it("does not count a decision that was undone", () => {
    const session = useScreeningSession.getState();
    for (const paperId of ["p1", "p2"]) {
      session.remember({ reviewId: "r", stage: "title_abstract", paperId, decisionId: paperId });
    }

    const undone = useScreeningSession.getState().takeBack("r", "title_abstract");

    expect(undone?.paperId).toBe("p2");
    expect(useScreeningSession.getState().decided).toBe(1);
  });

  it("counts nothing when there is nothing to undo", () => {
    expect(useScreeningSession.getState().takeBack("r", "full_text")).toBeUndefined();
    expect(useScreeningSession.getState().decided).toBe(0);
  });
});
