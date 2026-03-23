"use client";

import { useState } from "react";
import Link from "next/link";
import { Shield, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/api/v1/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });

      if (!res.ok) {
        setError("Something went wrong. Please try again.");
        setLoading(false);
        return;
      }

      setSubmitted(true);
    } catch {
      setError("Network error. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="flex justify-center mb-4">
            <Shield className="w-12 h-12 text-blue-600" />
          </div>
          <CardTitle className="text-2xl">Reset Password</CardTitle>
          <CardDescription>
            {submitted
              ? "Check your email for a reset link"
              : "Enter your email to receive a reset link"}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {submitted ? (
            <div className="space-y-4">
              <div className="bg-green-50 dark:bg-green-950 text-green-700 dark:text-green-400 text-sm p-3 rounded-lg">
                If an account exists with that email, we&apos;ve sent a password
                reset link. Please check your inbox.
              </div>
              <Link href="/login">
                <Button variant="outline" className="w-full">
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back to Sign In
                </Button>
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-400 text-sm p-3 rounded-lg">
                  {error}
                </div>
              )}
              <div className="space-y-2">
                <label
                  htmlFor="email"
                  className="text-sm font-medium text-gray-700 dark:text-gray-300"
                >
                  Email
                </label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
                />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Sending..." : "Send Reset Link"}
              </Button>
              <p className="text-center text-sm text-gray-500 dark:text-gray-400">
                <Link
                  href="/login"
                  className="text-blue-600 dark:text-blue-400 hover:underline font-medium"
                >
                  Back to Sign In
                </Link>
              </p>
            </form>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
