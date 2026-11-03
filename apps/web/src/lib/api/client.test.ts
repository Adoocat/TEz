import { describe, expect, it, vi } from "vitest";

import { createApiClient, isApiError } from "./client";

function fakeFetch(status: number, body: unknown) {
  return vi.fn<(request: Request) => Promise<Response>>(() =>
    Promise.resolve(
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

describe("createApiClient", () => {
  it("sends the bearer token and returns typed data", async () => {
    const fetch = fakeFetch(200, { status: "ok", version: "0.1.0" });
    const api = createApiClient({ baseUrl: "http://127.0.0.1:8787", token: "secret", fetch });

    const { data } = await api.GET("/health");

    expect(data?.version).toBe("0.1.0");
    const request = fetch.mock.calls[0]?.[0];
    expect(request?.url).toBe("http://127.0.0.1:8787/health");
    expect(request?.headers.get("Authorization")).toBe("Bearer secret");
  });

  it("fills path parameters", async () => {
    const fetch = fakeFetch(200, {});
    const api = createApiClient({ baseUrl: "http://api", token: "t", fetch });

    await api.GET("/jobs/{job_id}", { params: { path: { job_id: "j1" } } });

    expect(fetch.mock.calls[0]?.[0].url).toBe("http://api/jobs/j1");
  });

  it("exposes the error code, not text", async () => {
    const fetch = fakeFetch(409, { error: { code: "library.not_open", params: {} } });
    const api = createApiClient({ baseUrl: "http://api", token: "t", fetch });

    const { data, error } = await api.GET("/library");

    expect(data).toBeUndefined();
    expect(isApiError(error)).toBe(true);
    expect(isApiError(error) && error.error.code).toBe("library.not_open");
  });
});

describe("isApiError", () => {
  it("rejects values that are not the backend's error shape", () => {
    expect(isApiError(undefined)).toBe(false);
    expect(isApiError({ detail: "x" })).toBe(false);
    expect(isApiError({ error: { code: 1 } })).toBe(false);
  });
});
