import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";

import { useJobsStore } from "@/features/jobs/store";
import { fakeBackend, job, platformWith, readyPlatform } from "@/test/fakeBackend";

import { App } from "./App";
import { useLayoutStore } from "./layout/uiStore";

function openAt(hash: string) {
  window.location.hash = hash;
}

beforeEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
  useJobsStore.setState({ jobs: {} });
  useLayoutStore.setState({ sidebarOpen: true, inspectorOpen: true });
  openAt("#/library");
});

describe("Task 8 acceptance: language and theme", () => {
  it("survive a restart, because the library stores them", async () => {
    const user = userEvent.setup();
    const backend = fakeBackend({ language: "tr" });
    openAt("#/settings/general");
    const first = render(<App platform={readyPlatform} fetch={backend.fetch} />);

    await user.click(await screen.findByRole("radio", { name: "Koyu" }));
    await waitFor(() => {
      expect(document.documentElement.dataset.theme).toBe("dark");
    });
    await user.click(screen.getByRole("radio", { name: "English" }));
    expect(await screen.findByRole("heading", { level: 1, name: "General" })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe("en");

    // Restart on a "new device": nothing cached locally, only the library remembers.
    first.unmount();
    localStorage.clear();
    delete document.documentElement.dataset.theme;
    openAt("#/settings/general");
    render(<App platform={readyPlatform} fetch={backend.fetch} />);

    expect(await screen.findByRole("heading", { level: 1, name: "General" })).toBeInTheDocument();
    await waitFor(() => {
      expect(document.documentElement.dataset.theme).toBe("dark");
    });
    expect(screen.getByRole("radio", { name: "Dark" })).toBeChecked();
    expect(backend.settings).toEqual({ language: "en", theme: "dark", sources_email: null });
  });

  it("paints the last choice from this device before the backend answers", () => {
    localStorage.setItem("tez.theme", "dark");
    localStorage.setItem("tez.language", "en");

    render(<App platform={platformWith({ status: "starting" })} />);

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(screen.getByRole("status")).toHaveTextContent("Starting the backend…");
  });

  it("the top bar toggles the theme too", async () => {
    const user = userEvent.setup();
    const backend = fakeBackend({ language: "tr", theme: "light" });
    render(<App platform={readyPlatform} fetch={backend.fetch} />);

    await user.click(await screen.findByRole("button", { name: "Temayı değiştir" }));

    await waitFor(() => {
      expect(backend.settings.theme).toBe("dark");
    });
    expect(document.documentElement.dataset.theme).toBe("dark");
  });
});

describe("shell", () => {
  it("has the navigation rail, status bar and the library name", async () => {
    const backend = fakeBackend({ language: "tr" });
    render(<App platform={readyPlatform} fetch={backend.fetch} />);

    const nav = await screen.findByRole("navigation", { name: "Ana gezinme" });
    for (const label of [
      "Arama",
      "Kütüphane",
      "Eleme",
      "Okuyucu",
      "Notlar",
      "Matris",
      "İşler",
      "Ayarlar",
    ]) {
      expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(await screen.findByText("Kütüphane: TEz Library")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: "Kütüphane" })).toBeInTheDocument();
  });

  it("panels can be closed and stay closed", async () => {
    const user = userEvent.setup();
    localStorage.setItem("tez.language", "tr");
    const backend = fakeBackend({ language: "tr" });
    const first = render(<App platform={readyPlatform} fetch={backend.fetch} />);

    await user.click(await screen.findByRole("button", { name: "Denetçiyi aç/kapat" }));
    expect(screen.queryByRole("complementary", { name: "Denetçi" })).not.toBeInTheDocument();
    first.unmount();

    // What the next start reads back.
    const saved = JSON.parse(localStorage.getItem("tez.layout") ?? "{}") as {
      state?: { inspectorOpen?: boolean; sidebarOpen?: boolean };
    };
    expect(saved.state).toEqual({ inspectorOpen: false, sidebarOpen: true });
  });

  it("shows job progress from the event stream in the status bar", async () => {
    localStorage.setItem("tez.language", "tr");
    const backend = fakeBackend({ language: "tr" });
    render(<App platform={readyPlatform} fetch={backend.fetch} />);
    const indicator = await screen.findByTestId("jobs-indicator");
    expect(indicator).toHaveTextContent("Bekleyen iş yok");
    await waitFor(() => {
      expect(backend.requests.some((r) => r.path === "/jobs/events")).toBe(true);
    });

    act(() => {
      backend.emitJob(job({ id: "a", status: "running" }));
    });
    await waitFor(() => {
      expect(indicator).toHaveTextContent("1 iş çalışıyor");
    });

    act(() => {
      backend.emitJob(job({ id: "a", status: "failed" }));
    });
    await waitFor(() => {
      expect(indicator).toHaveTextContent("1 hatalı");
    });
  });
});

describe("backend start-up", () => {
  it("explains a library open in another window, in the user's language", () => {
    localStorage.setItem("tez.language", "tr");
    const failed = platformWith({
      status: "failed",
      error: { code: "library.locked", params: { pid: 4242, host: "LAB-PC", kind: "app" } },
    });

    render(<App platform={failed} />);

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("TEz başlatılamadı");
    expect(alert).toHaveTextContent("başka bir TEz penceresinde açık (süreç 4242, LAB-PC)");
  });
});

describe("settings: search sources", () => {
  it("saves an API key without ever showing it", async () => {
    const user = userEvent.setup();
    const backend = fakeBackend({ language: "tr" });
    openAt("#/settings/sources");
    render(<App platform={readyPlatform} fetch={backend.fetch} />);

    const input = await screen.findByLabelText("Semantic Scholar");
    await user.type(input, "  s2-secret-key ");
    const row = input.closest("li");
    if (!row) throw new Error("secret row missing");
    await user.click(within(row).getByRole("button", { name: "Kaydet" }));

    await waitFor(() => {
      expect(within(row).getByText("Kayıtlı")).toBeInTheDocument();
    });
    expect(backend.secrets.get("semantic_scholar_api_key")).toBe("s2-secret-key");
    expect(input).toHaveValue("");
    expect(document.body).not.toHaveTextContent("s2-secret-key");

    await user.click(within(row).getByRole("button", { name: "Kaldır" }));
    await waitFor(() => {
      expect(within(row).getByText("Kayıtlı değil")).toBeInTheDocument();
    });
  });

  it("checks the email before saving it", async () => {
    const user = userEvent.setup();
    const backend = fakeBackend({ language: "tr" });
    openAt("#/settings/sources");
    render(<App platform={readyPlatform} fetch={backend.fetch} />);

    const email = await screen.findByLabelText("E-posta adresi");
    await user.type(email, "demirkan@");
    const save = within(email.closest("form") ?? document.body).getByRole("button", {
      name: "Kaydet",
    });
    expect(screen.getByText("Geçerli bir e-posta adresi girin.")).toBeInTheDocument();
    expect(save).toBeDisabled();

    await user.type(email, "example.org");
    await user.click(save);

    await waitFor(() => {
      expect(backend.settings.sources_email).toBe("demirkan@example.org");
    });
  });
});
