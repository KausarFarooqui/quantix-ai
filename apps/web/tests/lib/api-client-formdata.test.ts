import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "@/lib/api-client";

describe("apiFetch with a FormData body", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends the FormData as-is and lets the browser set its own Content-Type", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 201,
      json: async () => ({ id: "dataset-1" }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const form = new FormData();
    form.append("file", new File(["a,b\n1,2"], "data.csv", { type: "text/csv" }));

    await apiFetch("/datasets/upload", { method: "POST", body: form });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.body).toBe(form);
    expect((init.headers as Record<string, string>)["Content-Type"]).toBeUndefined();
  });
});
