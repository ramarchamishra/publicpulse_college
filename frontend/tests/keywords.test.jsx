import React, { useState } from "react";
import { it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Keywords, Evidence, Sentiment } from "../src/components/ui";
const profile = {
  items: [
    {
      term: "battery life",
      tweet_count: 2,
      percentage: 50,
      other_tweet_count: 1,
      other_percentage: 10,
      distinctiveness_pp: 40,
      origin: "model",
    },
  ],
  omitted: [{ term: "subject", reason: "normalization_placeholder" }],
  tweet_count: 4,
  covered_tweet_count: 2,
  reference_tweet_count: 10,
  support_definition: "All keyword words.",
};
afterEach(() => vi.unstubAllGlobals());
it("filters real evidence requests when a keyword and sentiment are selected", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          data: { items: [], pages: 0, total: 0, page: 1, per_page: 10 },
        }),
      }),
  );
  function View() {
    const [selected, setSelected] = useState("");
    return (
      <>
        <Keywords
          words={["subject", "battery life"]}
          profile={profile}
          selected={selected}
          onSelect={setSelected}
        />
        <Evidence
          key={selected}
          path="/theme-runs/1/topics/0/tweets"
          keyword={selected}
        />
      </>
    );
  }
  render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <View />
    </QueryClientProvider>,
  );
  await userEvent.click(
    screen.getByRole("button", { name: "battery life 2 tweets" }),
  );
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      "/api/theme-runs/1/topics/0/tweets?page=1&per_page=10&keyword=battery+life",
      expect.anything(),
    ),
  );
  await userEvent.selectOptions(
    screen.getByRole("combobox", { name: "Sentiment" }),
    "negative",
  );
  await waitFor(() =>
    expect(fetch).toHaveBeenCalledWith(
      "/api/theme-runs/1/topics/0/tweets?page=1&per_page=10&sentiment=negative&keyword=battery+life",
      expect.anything(),
    ),
  );
  expect(
    screen.getByRole("button", { name: "battery life 2 tweets" }),
  ).toHaveAttribute("aria-pressed", "true");
  await userEvent.click(
    screen.getByRole("button", { name: "Clear keyword filter" }),
  );
  expect(
    screen.queryByRole("button", { name: "Clear keyword filter" }),
  ).not.toBeInTheDocument();
});
it("discloses sparse support, original terms and missing sentiment coverage", () => {
  render(<Keywords words={["subject", "battery life"]} profile={profile} />);
  expect(screen.getByText(/cover 2 of 4 unique tweets/)).toBeInTheDocument();
  expect(screen.getByText(/normalization placeholder/)).toBeInTheDocument();
  const data = {
    analyzed_count: 1,
    missing_count: 9,
    positive: { count: 1, percentage: 100 },
    neutral: { count: 0, percentage: 0 },
    negative: { count: 0, percentage: 0 },
  };
  render(<Sentiment data={data} />);
  expect(screen.getByText(/Incomplete coverage/)).toBeInTheDocument();
  expect(screen.getByText(/not necessarily support/)).toBeInTheDocument();
});
