import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { App } from "@/app/App";
import { useLayoutStore } from "@/app/layout/uiStore";
import { useJobsStore } from "@/features/jobs/store";
import { useActiveReviewStore } from "@/features/reviews/store";
import { fakeBackend, readyPlatform, review, type FakeBackend } from "@/test/fakeBackend";

import { useUploadStore } from "./store";

beforeEach(() => {
  localStorage.clear();
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  useActiveReviewStore.setState({ activeReviewId: null });
  useUploadStore.setState({ notices: [] });
  window.location.hash = "#/settings";
});

function setUp() {
  const backend = fakeBackend({ language: "en" });
  backend.reviews.push(review());
  render(<App platform={readyPlatform} fetch={backend.fetch} />);
  return backend;
}

function pdf(name: string, body = "%PDF-1.4 test") {
  return new File([body], name, { type: "application/pdf" });
}

/** jsdom has no DataTransfer; this is the part the drop handler reads. */
function drop(files: File[]) {
  const dataTransfer = { types: ["Files"], files };
  fireEvent.dragEnter(window, { dataTransfer });
  fireEvent.drop(window, { dataTransfer });
}

function uploads(backend: FakeBackend) {
  return backend.requests.filter((r) => r.path === "/pdfs");
}

describe("dropping PDFs on the window", () => {
  it("shows a veil while files are dragged over", async () => {
    setUp();
    await screen.findByRole("heading", { level: 1, name: "General" });

    fireEvent.dragEnter(window, { dataTransfer: { types: ["Files"], files: [] } });
    expect(screen.getByText("Drop PDFs to add them to the library")).toBeInTheDocument();

    fireEvent.dragLeave(window, { dataTransfer: { types: ["Files"], files: [] } });
    expect(screen.queryByText("Drop PDFs to add them to the library")).not.toBeInTheDocument();
  });

  it("uploads each PDF as the raw body and reports what became of it", async () => {
    const backend = setUp();
    backend.pdfReplies = [
      { status: "added" },
      { status: "duplicate" },
      {
        error: { code: "pdf.not_a_pdf", params: { file_name: "fake.pdf" } },
        httpStatus: 422,
      },
    ];
    await screen.findByRole("heading", { level: 1, name: "General" });

    act(() => {
      drop([pdf("kim-2024.pdf"), new File(["x"], "notes.txt"), pdf("copy.pdf"), pdf("fake.pdf")]);
    });

    const notices = await screen.findByRole("list");
    await waitFor(() => {
      expect(within(notices).getByText("Added to the inbox.")).toBeInTheDocument();
      expect(
        within(notices).getByText("Already in the library: nothing was copied."),
      ).toBeInTheDocument();
      expect(within(notices).getByText("fake.pdf is not a PDF file.")).toBeInTheDocument();
    });
    // The text file was not sent.
    expect(uploads(backend)).toHaveLength(3);
    const first = uploads(backend)[0];
    expect(new TextDecoder().decode(first?.body as ArrayBuffer)).toBe("%PDF-1.4 test");
  });

  it("lets a failure notice be dismissed", async () => {
    const user = userEvent.setup();
    const backend = setUp();
    backend.pdfReplies = [
      { error: { code: "pdf.too_large", params: { file_name: "big.pdf" } }, httpStatus: 413 },
    ];
    await screen.findByRole("heading", { level: 1, name: "General" });

    act(() => {
      drop([pdf("big.pdf")]);
    });
    await screen.findByText("big.pdf is too large to add.");
    await user.click(screen.getByRole("button", { name: "Dismiss" }));

    expect(screen.queryByText("big.pdf is too large to add.")).not.toBeInTheDocument();
  });
});
