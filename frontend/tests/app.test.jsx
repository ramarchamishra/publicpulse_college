import React from "react";
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "../src/App";
import { api } from "../src/services/api";
const sentiment = {
  analyzed_count: 1,
  missing_count: 2,
  positive: { count: 1, percentage: 100 },
  neutral: { count: 0, percentage: 0 },
  negative: { count: 0, percentage: 0 },
};
const search = {
  id: 1,
  topic: "Test topic",
  tweet_count: 3,
  run_count: 0,
  sentiment,
  mode: "Latest",
  scraped_at: "2026-01-01",
  requested_limit: 10,
};
const page = (items) => ({
  items,
  page: 1,
  per_page: 20,
  total: items.length,
  pages: 1,
});
function mount(path = "/") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
function mock(extra = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url, options) => {
      let value = {
        "/api/health": { status: "ok" },
        "/api/dashboard": {
          search_count: 1,
          tweet_count: 3,
          theme_run_count: 0,
          sentiment,
          recent_searches: [search],
        },
        "/api/searches/1": search,
        ...extra,
      }[url];
      if (value === undefined)
        value = url.includes("/jobs?")
          ? page([])
          : url.includes("/searches?")
            ? page([search])
            : url.includes("/theme-runs?")
              ? page([])
              : page([]);
      if (typeof value === "function") value = value(options);
      return { ok: true, status: 200, json: async () => ({ data: value }) };
    }),
  );
}
afterEach(() => vi.unstubAllGlobals());
describe("connected application workflows", () => {
  it("shows real response metrics and navigates to a search", async () => {
    mock();
    mount();
    expect(await screen.findByText("Test topic")).toBeInTheDocument();
    await userEvent.click(screen.getByText("Test topic"));
    expect(await screen.findByText("Tweet explorer")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Analyze missing sentiment" }),
    ).toBeInTheDocument();
  });
  it("submits collection fields and displays job failure", async () => {
    mock({
      "/api/searches": (opts) => {
        expect(JSON.parse(opts.body)).toEqual({
          topic: "New topic",
          limit: 100,
          mode: "Latest",
        });
        return { id: "job1" };
      },
      "/api/jobs/job1": {
        id: "job1",
        kind: "collection",
        status: "failed",
        inputs: { topic: "New topic" },
        created_at: "2026-01-01",
        error: "Session unavailable",
      },
    });
    mount("/searches?new=1");
    await userEvent.type(screen.getByLabelText("Topic"), "New topic");
    await userEvent.click(
      screen.getByRole("button", { name: "Start collection" }),
    );
    expect(await screen.findByText("Session unavailable")).toBeInTheDocument();
  });
  it("disables comparison until two different searches are selected", async () => {
    mock();
    mount("/compare");
    await screen.findByRole("combobox", { name: "Search A" });
    expect(
      screen.getByRole("button", { name: "Compare topics" }),
    ).toBeDisabled();
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Search A" }),
      "1",
    );
    expect(
      screen
        .getByRole("combobox", { name: "Search B" })
        .querySelector('option[value="1"]'),
    ).toBeDisabled();
  });
  it("loads saved themes and requests paginated evidence", async () => {
    mock({
      "/api/theme-runs/5": {
        run: { id: 5, created_at: "2026-01-01", embedding_model: "existing" },
        theme_count: 1,
        tweet_count: 3,
        clustered_count: 2,
        noise_count: 1,
        clustered_percentage: 66.7,
        themes: [
          {
            bertopic_topic_id: 0,
            name: "Saved discussion",
            tweet_count: 2,
            discussion_share_percentage: 66.7,
            keywords: [["word", 0.5]],
            sentiment,
          },
        ],
        noise: {
          bertopic_topic_id: -1,
          name: "Unclustered tweets",
          tweet_count: 1,
          sentiment,
        },
      },
    });
    mount("/themes?search=1&run=5");
    expect(
      await screen.findByRole("heading", { name: "Saved discussion" }),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        "/api/theme-runs/5/topics/0/tweets?page=1&per_page=10",
        expect.anything(),
      ),
    );
  });
  it("reports unavailable backend without crashing", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    mount();
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Unable to reach PublicPulse",
    );
  });
  it("rejects malformed API envelopes", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue({
          ok: true,
          status: 200,
          json: async () => ({ unexpected: true }),
        }),
    );
    await expect(api("/health")).rejects.toThrow("backend is unavailable");
  });
});
