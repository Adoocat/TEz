// Task 37: adding grey literature by hand from the review panel.
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "@/app/App";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import { fakeBackend, readyPlatform, review } from "@/test/fakeBackend";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useActiveReviewStore.setState({ activeReviewId: null });
  window.location.hash = "#/review";
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {
        return undefined;
      }
      unobserve() {
        return undefined;
      }
      disconnect() {
        return undefined;
      }
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function open(matched = false) {
  const backend = fakeBackend({ language: "tr" });
  backend.reviews = [review({ id: "review-1" })];
  const posted: unknown[] = [];
  const entries: unknown[] = [];
  const fetch = async (request: Request) => {
    const path = new URL(request.url, "http://test").pathname;
    if (path === "/reviews/review-1/grey-literature" && request.method === "POST") {
      const body = (await request.json()) as { title: string; source: string };
      posted.push(body);
      entries.push({
        search_id: "s1",
        found_via: "thesis",
        source: body.source,
        executed_at: "2026-11-16T12:00:00+00:00",
        file_name: null,
        records: 1,
        titles: [body.title],
      });
      return json(
        {
          paper_id: "p1",
          search_id: "s1",
          found_via: "thesis",
          matched_existing: matched,
          added_to_review: !matched,
        },
        201,
      );
    }
    if (path === "/reviews/review-1/grey-literature") return json(entries);
    if (path.startsWith("/reviews/review-1/snowball")) return json([]);
    return backend.fetch(request);
  };
  render(<App platform={readyPlatform} fetch={fetch} />);
  return { posted, user: userEvent.setup() };
}

describe("grey literature on the review panel", () => {
  it("adds a thesis by hand, in Turkish, and lists it in its box", async () => {
    const { posted, user } = open();
    const section = await screen.findByRole("region", { name: "Gri literatür" });
    const form = within(section).getByRole("form", { name: "Kayıt ekle" });

    expect(within(form).getByRole("combobox", { name: "PRISMA kutusu" })).toHaveDisplayValue(
      "Türe göre (Tezler)",
    );
    await user.type(within(form).getByRole("textbox", { name: "Başlık" }), "Kod İnceleme Tezi");
    await user.type(
      within(form).getByRole("textbox", { name: "Bulunduğu yer" }),
      "YÖK Ulusal Tez Merkezi",
    );
    await user.type(
      within(form).getByRole("textbox", { name: "Yazarlar" }),
      "Yılmaz, Ayşe; Demir, Can",
    );
    await user.type(within(form).getByRole("textbox", { name: "Yıl" }), "2025");
    await user.click(within(form).getByRole("button", { name: "Kayıt ekle" }));

    await waitFor(() => {
      expect(posted[0]).toMatchObject({
        kind: "thesis",
        found_via: null,
        source: "YÖK Ulusal Tez Merkezi",
        title: "Kod İnceleme Tezi",
        authors: ["Yılmaz, Ayşe", "Demir, Can"],
        year: 2025,
      });
    });
    expect(await within(form).findByRole("status")).toHaveTextContent(
      "Review'a ve elemeye eklendi.",
    );
    const list = await within(section).findByRole("list", { name: "Bulunan gri literatür" });
    expect(list).toHaveTextContent("Tezler · YÖK Ulusal Tez Merkezi");
    expect(list).toHaveTextContent("Kod İnceleme Tezi");
  });

  it("says when the record was already in the library", async () => {
    const { user } = open(true);
    const section = await screen.findByRole("region", { name: "Gri literatür" });
    const form = within(section).getByRole("form", { name: "Kayıt ekle" });

    await user.type(within(form).getByRole("textbox", { name: "Başlık" }), "Bilinen tez");
    await user.type(within(form).getByRole("textbox", { name: "Bulunduğu yer" }), "YÖK");
    await user.click(within(form).getByRole("button", { name: "Kayıt ekle" }));

    expect(await within(form).findByRole("status")).toHaveTextContent(
      "Kütüphanede bu kayıt zaten vardı: tekrar olarak sayılır.",
    );
  });
});
