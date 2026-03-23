import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DashboardPage from "./page";

// Mock the hooks module
const mockUseDashboardStats = vi.fn();
const mockUseDeliverabilityStats = vi.fn();
const mockUseSequencesAnalytics = vi.fn();
const mockUseOutreachDaily = vi.fn();
const mockUseRecentActivity = vi.fn();

vi.mock("@/lib/hooks", () => ({
  useDashboardStats: () => mockUseDashboardStats(),
  useDeliverabilityStats: () => mockUseDeliverabilityStats(),
  useSequencesAnalytics: () => mockUseSequencesAnalytics(),
  useOutreachDaily: () => mockUseOutreachDaily(),
  useRecentActivity: () => mockUseRecentActivity(),
}));

function renderWithProvider(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

function defaultHookState() {
  return { data: undefined, isLoading: false, error: null };
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseDashboardStats.mockReturnValue(defaultHookState());
    mockUseDeliverabilityStats.mockReturnValue(defaultHookState());
    mockUseSequencesAnalytics.mockReturnValue(defaultHookState());
    mockUseOutreachDaily.mockReturnValue(defaultHookState());
    mockUseRecentActivity.mockReturnValue(defaultHookState());
  });

  it("renders loading skeletons while data loads", () => {
    mockUseDashboardStats.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });
    mockUseDeliverabilityStats.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });
    mockUseOutreachDaily.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });
    mockUseRecentActivity.mockReturnValue({
      data: undefined,
      isLoading: true,
      error: null,
    });

    renderWithProvider(<DashboardPage />);

    // Skeletons have animate-pulse class
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it("renders stats cards with fetched data", () => {
    mockUseDashboardStats.mockReturnValue({
      data: {
        total_leads: 150,
        active_consents: 75,
        touches_sent: 500,
        response_rate: 0.12,
      },
      isLoading: false,
      error: null,
    });

    renderWithProvider(<DashboardPage />);

    expect(screen.getByText("150")).toBeInTheDocument();
    expect(screen.getByText("75")).toBeInTheDocument();
    expect(screen.getByText("500")).toBeInTheDocument();
    expect(screen.getByText("12.0%")).toBeInTheDocument();
  });

  it("renders stat card labels", () => {
    mockUseDashboardStats.mockReturnValue({
      data: {
        total_leads: 0,
        active_consents: 0,
        touches_sent: 0,
        response_rate: 0,
      },
      isLoading: false,
      error: null,
    });

    renderWithProvider(<DashboardPage />);

    expect(screen.getByText("Total Leads")).toBeInTheDocument();
    expect(screen.getByText("Active Consents")).toBeInTheDocument();
    expect(screen.getByText("Touches Sent")).toBeInTheDocument();
    expect(screen.getByText("Response Rate")).toBeInTheDocument();
  });

  it("shows empty state when no outreach data", () => {
    mockUseOutreachDaily.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });

    renderWithProvider(<DashboardPage />);
    expect(screen.getByText(/no outreach data yet/i)).toBeInTheDocument();
  });

  it("shows error state on outreach API failure", () => {
    mockUseOutreachDaily.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("API Error"),
    });

    renderWithProvider(<DashboardPage />);
    expect(
      screen.getByText(/failed to load outreach data/i)
    ).toBeInTheDocument();
  });

  it("shows error state when stats fail", () => {
    mockUseDashboardStats.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("API Error"),
    });

    renderWithProvider(<DashboardPage />);
    // Stats errors show as "—" for values
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
  });

  it("shows empty state for no recent activity", () => {
    mockUseRecentActivity.mockReturnValue({
      data: [],
      isLoading: false,
      error: null,
    });

    renderWithProvider(<DashboardPage />);
    expect(screen.getByText(/no recent activity/i)).toBeInTheDocument();
  });

  it("shows error state for failed recent activity", () => {
    mockUseRecentActivity.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("API Error"),
    });

    renderWithProvider(<DashboardPage />);
    expect(
      screen.getByText(/failed to load recent activity/i)
    ).toBeInTheDocument();
  });

  it("renders deliverability health when data is available", () => {
    mockUseDeliverabilityStats.mockReturnValue({
      data: {
        total_sent: 1000,
        total_bounced: 20,
        bounce_rate: 0.02,
        spam_complaints: 1,
        spam_rate: 0.001,
        warmup_active: 2,
        warmup_completed: 5,
      },
      isLoading: false,
      error: null,
    });

    renderWithProvider(<DashboardPage />);
    expect(screen.getByText("Deliverability Health")).toBeInTheDocument();
    expect(screen.getByText("Bounce Rate")).toBeInTheDocument();
    expect(screen.getByText("Spam Rate")).toBeInTheDocument();
  });

  it("shows empty state for no sequence data", () => {
    mockUseSequencesAnalytics.mockReturnValue({
      data: { sequences: [] },
      isLoading: false,
      error: null,
    });

    renderWithProvider(<DashboardPage />);
    expect(screen.getByText(/no sequence data yet/i)).toBeInTheDocument();
  });

  it("renders quick action buttons", () => {
    renderWithProvider(<DashboardPage />);
    expect(screen.getByText("Import Leads")).toBeInTheDocument();
    expect(screen.getByText("Create Sequence")).toBeInTheDocument();
    expect(screen.getByText("Compliance Check")).toBeInTheDocument();
  });

  it("renders outreach chart with data", () => {
    mockUseOutreachDaily.mockReturnValue({
      data: [
        { day: "Mon", email: 10, sms: 5, linkedin: 3 },
        { day: "Tue", email: 15, sms: 8, linkedin: 4 },
      ],
      isLoading: false,
      error: null,
    });

    renderWithProvider(<DashboardPage />);
    expect(screen.getByText("Outreach Volume (7d)")).toBeInTheDocument();
    // Chart legends
    expect(screen.getByText("Email")).toBeInTheDocument();
    expect(screen.getByText("SMS")).toBeInTheDocument();
    expect(screen.getByText("LinkedIn")).toBeInTheDocument();
  });

  it("renders recent activity items", () => {
    mockUseRecentActivity.mockReturnValue({
      data: [
        { id: 1, text: "Sent email to john@acme.com", time: "2 min ago", type: "lead" },
        { id: 2, text: "Sequence started", time: "5 min ago", type: "sequence" },
      ],
      isLoading: false,
      error: null,
    });

    renderWithProvider(<DashboardPage />);
    expect(
      screen.getByText("Sent email to john@acme.com")
    ).toBeInTheDocument();
    expect(screen.getByText("Sequence started")).toBeInTheDocument();
  });
});
