import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SequencesPage from "./page";

const mockUseSequences = vi.fn();
const mockUseSequencePerformance = vi.fn();
const mockToast = vi.fn();

vi.mock("@/lib/hooks", () => ({
  useSequences: (...args: unknown[]) => mockUseSequences(...args),
  useSequencePerformance: () => mockUseSequencePerformance(),
}));

vi.mock("@/lib/hooks/use-toast", () => ({
  useToast: () => ({ toast: mockToast, toasts: [], dismiss: vi.fn() }),
}));

const mockCreate = vi.fn();
const mockDelete = vi.fn();
const mockUpdate = vi.fn();

vi.mock("@/lib/api", () => ({
  sequencesApi: {
    create: (...args: unknown[]) => mockCreate(...args),
    delete: (...args: unknown[]) => mockDelete(...args),
    update: (...args: unknown[]) => mockUpdate(...args),
  },
}));

vi.mock("@tanstack/react-query", async () => {
  const actual = await vi.importActual("@tanstack/react-query");
  return {
    ...actual,
    useQueryClient: () => ({
      invalidateQueries: vi.fn(),
    }),
  };
});

function renderWithProvider(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

const mockSequences = [
  {
    id: "seq-1",
    name: "Q4 Enterprise Outreach",
    description: "Automated enterprise outreach",
    status: "active",
    created_at: "2024-01-15T10:00:00Z",
    updated_at: "2024-01-15T10:00:00Z",
    steps: [{ id: "step-1" }, { id: "step-2" }],
    enrolled_count: 50,
    visual_config: null,
    ai_generated: false,
    ai_generation_prompt: null,
    ai_generation_metadata: null,
  },
  {
    id: "seq-2",
    name: "Cold Email Blast",
    description: "Initial cold outreach",
    status: "draft",
    created_at: "2024-01-10T10:00:00Z",
    updated_at: "2024-01-10T10:00:00Z",
    steps: [{ id: "step-3" }],
    enrolled_count: 0,
    visual_config: null,
    ai_generated: true,
    ai_generation_prompt: "cold email",
    ai_generation_metadata: null,
  },
  {
    id: "seq-3",
    name: "Paused Sequence",
    description: null,
    status: "paused",
    created_at: "2024-01-05T10:00:00Z",
    updated_at: "2024-01-05T10:00:00Z",
    steps: [],
    enrolled_count: 10,
    visual_config: null,
    ai_generated: false,
    ai_generation_prompt: null,
    ai_generation_metadata: null,
  },
];

const mockPerfData = [
  { sequence_id: "seq-1", total_sends: 100, opens: 45, replies: 12, bounces: 3 },
  { sequence_id: "seq-2", total_sends: 0, opens: 0, replies: 0, bounces: 0 },
];

describe("SequencesPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseSequences.mockReturnValue({
      data: { items: mockSequences, total: 3, page: 1, page_size: 12 },
      isLoading: false,
      error: null,
    });
    mockUseSequencePerformance.mockReturnValue({
      data: mockPerfData,
      isLoading: false,
      error: null,
    });
  });

  it("renders sequence list", () => {
    renderWithProvider(<SequencesPage />);
    expect(screen.getByText("Q4 Enterprise Outreach")).toBeInTheDocument();
    expect(screen.getByText("Cold Email Blast")).toBeInTheDocument();
    expect(screen.getByText("Paused Sequence")).toBeInTheDocument();
  });

  it("renders loading skeletons", () => {
    mockUseSequences.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });

    renderWithProvider(<SequencesPage />);
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders error state", () => {
    mockUseSequences.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("API Error"),
    });

    renderWithProvider(<SequencesPage />);
    expect(
      screen.getByText(/failed to load sequences/i)
    ).toBeInTheDocument();
  });

  it("renders empty state when no sequences", () => {
    mockUseSequences.mockReturnValue({
      data: { items: [], total: 0, page: 1, page_size: 12 },
      isLoading: false,
      error: null,
    });

    renderWithProvider(<SequencesPage />);
    expect(screen.getByText(/no sequences yet/i)).toBeInTheDocument();
  });

  it("displays performance metrics correctly", () => {
    renderWithProvider(<SequencesPage />);

    // seq-1 has 45/100 = 45% open rate, 12/100 = 12% reply rate
    expect(screen.getByText("45%")).toBeInTheDocument();
    expect(screen.getByText("12%")).toBeInTheDocument();
  });

  it("displays status badges", () => {
    renderWithProvider(<SequencesPage />);
    expect(screen.getAllByText("active").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("draft").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("paused").length).toBeGreaterThanOrEqual(1);
  });

  it("shows step and enrollment counts", () => {
    renderWithProvider(<SequencesPage />);
    expect(screen.getByText("2 steps")).toBeInTheDocument();
    expect(screen.getByText("50 enrolled")).toBeInTheDocument();
  });

  it("shows AI badge for AI-generated sequence", () => {
    renderWithProvider(<SequencesPage />);
    expect(screen.getByText("AI")).toBeInTheDocument();
  });

  it("renders status filter tabs", () => {
    renderWithProvider(<SequencesPage />);
    expect(screen.getByRole("tablist")).toBeInTheDocument();
    expect(screen.getAllByText("all").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("active").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("draft").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("paused").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("archived").length).toBeGreaterThanOrEqual(1);
  });

  it("calls create endpoint when creating a sequence", async () => {
    mockCreate.mockResolvedValue({ data: { id: "new-seq" } });
    const user = userEvent.setup();

    renderWithProvider(<SequencesPage />);

    // Click "New Sequence" button
    await user.click(screen.getByText(/new sequence/i));

    // Fill in the name
    const nameInput = screen.getByPlaceholderText(/q4 enterprise/i);
    await user.type(nameInput, "My New Sequence");

    // Click Create
    await user.click(screen.getByRole("button", { name: /^create$/i }));

    await waitFor(() => {
      expect(mockCreate).toHaveBeenCalledWith({
        name: "My New Sequence",
        description: undefined,
      });
    });
  });

  it("calls delete endpoint on delete action", async () => {
    mockDelete.mockResolvedValue({});
    const user = userEvent.setup();

    renderWithProvider(<SequencesPage />);

    // Find and click the action dropdown for first sequence
    const actionButtons = screen.getAllByLabelText("Sequence actions");
    await user.click(actionButtons[0]);

    // Click Delete
    await user.click(screen.getByText("Delete"));

    await waitFor(() => {
      expect(mockDelete).toHaveBeenCalledWith("seq-1");
    });
  });

  it("calls update endpoint on pause action", async () => {
    mockUpdate.mockResolvedValue({});
    const user = userEvent.setup();

    renderWithProvider(<SequencesPage />);

    // Find first sequence (active) and click its actions
    const actionButtons = screen.getAllByLabelText("Sequence actions");
    await user.click(actionButtons[0]);

    // Click Pause
    await user.click(screen.getByText("Pause"));

    await waitFor(() => {
      expect(mockUpdate).toHaveBeenCalledWith("seq-1", { status: "paused" });
    });
  });

  it("renders New Sequence button", () => {
    renderWithProvider(<SequencesPage />);
    expect(screen.getByText(/new sequence/i)).toBeInTheDocument();
  });
});
