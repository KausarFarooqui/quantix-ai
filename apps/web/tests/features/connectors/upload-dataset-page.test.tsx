import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import UploadDatasetPage from "@/app/(app)/datasets/upload/page";
import { renderWithQueryClient } from "../../test-utils";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
}));

const uploadFileDataset = vi.fn();
vi.mock("@/features/connectors/api", () => ({
  connectorsApi: {
    uploadFileDataset: (...args: unknown[]) => uploadFileDataset(...args),
  },
}));

describe("UploadDatasetPage", () => {
  beforeEach(() => {
    push.mockClear();
    uploadFileDataset.mockReset();
  });

  it("requires a file before submitting", async () => {
    const user = userEvent.setup();
    renderWithQueryClient(<UploadDatasetPage />);

    await user.click(screen.getByRole("button", { name: "Upload" }));

    expect(await screen.findByText("Choose a file to upload")).toBeInTheDocument();
    expect(uploadFileDataset).not.toHaveBeenCalled();
  });

  it("uploads the selected file with an optional dataset name", async () => {
    uploadFileDataset.mockResolvedValue({
      id: "dataset-1",
      data_source_id: "src-1",
      name: "orders",
      table_identifier: "orders.csv",
      schema: [],
      row_count: 10,
      size_bytes: 100,
      status: "ready",
      status_message: null,
      last_synced_at: "2026-08-01T00:00:00Z",
      created_at: "2026-08-01T00:00:00Z",
    });
    const user = userEvent.setup();
    renderWithQueryClient(<UploadDatasetPage />);

    const file = new File(["a,b\n1,2"], "orders.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("File"), file);
    await user.type(screen.getByLabelText(/Dataset name/), "Orders");
    await user.click(screen.getByRole("button", { name: "Upload" }));

    await waitFor(() =>
      expect(uploadFileDataset).toHaveBeenCalledWith({ file, datasetName: "Orders" }),
    );
    await waitFor(() => expect(push).toHaveBeenCalledWith("/datasets/dataset-1"));
  });
});
