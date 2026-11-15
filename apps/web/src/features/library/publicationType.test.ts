// Task 28: a "thesis" filter keeps every thesis; a degree keeps only its own.
import { describe, expect, it } from "vitest";

import { hasPublicationType, presentTypes, publicationTypeOf } from "./publicationType";

const masters = { venue_type: "thesis", thesis_type: "masters" } as const;
const doctoral = { venue_type: "thesis", thesis_type: "doctoral" } as const;
const unknown = { venue_type: "thesis", thesis_type: null } as const;
const book = { venue_type: "book", thesis_type: null } as const;

describe("publication types", () => {
  it("match theses by degree or as a whole", () => {
    expect([masters, doctoral, unknown, book].map((r) => hasPublicationType(r, "thesis"))).toEqual([
      true,
      true,
      true,
      false,
    ]);
    expect(
      [masters, doctoral, unknown].map((r) => hasPublicationType(r, "thesis_masters")),
    ).toEqual([true, false, false]);
    expect(hasPublicationType(book, "book")).toBe(true);
  });

  it("label a row by its most precise type", () => {
    expect([masters, unknown, book].map(publicationTypeOf)).toEqual([
      "thesis_masters",
      "thesis",
      "book",
    ]);
  });

  it("offer only the types present, in menu order", () => {
    expect(presentTypes([book, doctoral])).toEqual(["book", "thesis", "thesis_doctoral"]);
  });
});
