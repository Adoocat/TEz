import { afterEach, describe, expect, it, vi } from "vitest";

import { browserPlatform } from "./browser";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("the browser platform", () => {
  it("opens outside links in a new tab, cut off from this page", async () => {
    const open = vi.spyOn(window, "open").mockReturnValue(null);

    await browserPlatform.openExternal("https://doi.org/10.1000/abc");

    expect(open).toHaveBeenCalledWith(
      "https://doi.org/10.1000/abc",
      "_blank",
      "noopener,noreferrer",
    );
  });
});
