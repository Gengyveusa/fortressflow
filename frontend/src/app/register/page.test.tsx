import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RegisterPage from "./page";

const mockPush = vi.fn();
const mockRefresh = vi.fn();
const mockSignIn = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: mockPush,
    refresh: mockRefresh,
  }),
}));

vi.mock("next-auth/react", () => ({
  signIn: (...args: unknown[]) => mockSignIn(...args),
}));

describe("RegisterPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn();
  });

  it("renders all form fields", () => {
    render(<RegisterPage />);
    expect(screen.getByLabelText(/full name/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^password$/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
  });

  it("renders create account button", () => {
    render(<RegisterPage />);
    expect(
      screen.getByRole("button", { name: /create account/i })
    ).toBeInTheDocument();
  });

  it("shows email validation error for invalid email", async () => {
    const user = userEvent.setup();
    render(<RegisterPage />);

    const emailInput = screen.getByLabelText(/^email$/i);
    await user.type(emailInput, "notavalidemail");

    await waitFor(() => {
      expect(
        screen.getByText(/please enter a valid email address/i)
      ).toBeInTheDocument();
    });
  });

  it("does not show email error for valid email", async () => {
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText(/^email$/i), "test@example.com");

    expect(
      screen.queryByText(/please enter a valid email address/i)
    ).not.toBeInTheDocument();
  });

  it("shows password strength indicator", async () => {
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText(/^password$/i), "a");
    expect(screen.getByText(/weak/i)).toBeInTheDocument();

    await user.clear(screen.getByLabelText(/^password$/i));
    await user.type(screen.getByLabelText(/^password$/i), "Abcdefgh12!@");
    expect(screen.getByText(/strong/i)).toBeInTheDocument();
  });

  it("shows passwords do not match error", async () => {
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText(/^password$/i), "Password1!");
    await user.type(
      screen.getByLabelText(/confirm password/i),
      "DifferentPass"
    );

    await waitFor(() => {
      expect(
        screen.getByText(/passwords do not match/i)
      ).toBeInTheDocument();
    });
  });

  it("does not show mismatch when passwords match", async () => {
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText(/^password$/i), "Password1!");
    await user.type(screen.getByLabelText(/confirm password/i), "Password1!");

    expect(
      screen.queryByText(/passwords do not match/i)
    ).not.toBeInTheDocument();
  });

  it("shows error when registration fails", async () => {
    vi.mocked(global.fetch).mockResolvedValue({
      ok: false,
      json: () => Promise.resolve({ detail: "Registration failed" }),
    } as Response);

    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText(/^email$/i), "test@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "Password1!");
    await user.type(screen.getByLabelText(/confirm password/i), "Password1!");
    await user.click(
      screen.getByRole("button", { name: /create account/i })
    );

    await waitFor(() => {
      expect(screen.getByText(/registration failed/i)).toBeInTheDocument();
    });
  });

  it("calls fetch and signIn on successful registration", async () => {
    vi.mocked(global.fetch).mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({}),
    } as Response);
    mockSignIn.mockResolvedValue({ error: null });

    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText(/^email$/i), "new@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "StrongPass1!");
    await user.type(
      screen.getByLabelText(/confirm password/i),
      "StrongPass1!"
    );
    await user.click(
      screen.getByRole("button", { name: /create account/i })
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/v1/auth/register"),
        expect.objectContaining({ method: "POST" })
      );
    });

    await waitFor(() => {
      expect(mockSignIn).toHaveBeenCalledWith("credentials", {
        email: "new@example.com",
        password: "StrongPass1!",
        redirect: false,
      });
    });
  });

  it("shows error for password less than 8 characters on submit", async () => {
    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText(/^email$/i), "test@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "Short1!");
    await user.type(screen.getByLabelText(/confirm password/i), "Short1!");
    await user.click(
      screen.getByRole("button", { name: /create account/i })
    );

    await waitFor(() => {
      expect(
        screen.getByText(/password must be at least 8 characters/i)
      ).toBeInTheDocument();
    });
  });

  it("shows network error on fetch failure", async () => {
    vi.mocked(global.fetch).mockRejectedValue(new Error("Network error"));

    const user = userEvent.setup();
    render(<RegisterPage />);

    await user.type(screen.getByLabelText(/^email$/i), "test@example.com");
    await user.type(screen.getByLabelText(/^password$/i), "StrongPass1!");
    await user.type(
      screen.getByLabelText(/confirm password/i),
      "StrongPass1!"
    );
    await user.click(
      screen.getByRole("button", { name: /create account/i })
    );

    await waitFor(() => {
      expect(
        screen.getByText(/network error/i)
      ).toBeInTheDocument();
    });
  });

  it("has link to sign in page", () => {
    render(<RegisterPage />);
    expect(screen.getByText(/sign in/i)).toBeInTheDocument();
  });
});
