"use client";

import { useState } from "react";
import Link from "next/link";
import { Shield, CheckCircle2, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SmsConsentPage() {
  const [phone, setPhone] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (!agreed) {
      setError("You must agree to receive SMS notifications to continue.");
      return;
    }

    const cleaned = phone.replace(/\D/g, "");
    if (cleaned.length < 10 || cleaned.length > 15) {
      setError("Please enter a valid phone number.");
      return;
    }

    setLoading(true);

    try {
      const res = await fetch("/api/v1/sms/consent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phone: cleaned, consented: true }),
      });

      if (!res.ok) {
        throw new Error("Failed to submit consent");
      }

      setSubmitted(true);
    } catch {
      setError("Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950 px-4">
        <Card className="w-full max-w-md dark:bg-gray-900 dark:border-gray-800">
          <CardContent className="pt-8 pb-8 text-center">
            <CheckCircle2 className="w-16 h-16 text-green-500 mx-auto mb-4" />
            <h2 className="text-xl font-semibold dark:text-gray-100 mb-2">
              Consent Recorded
            </h2>
            <p className="text-gray-600 dark:text-gray-400 text-sm">
              You have successfully opted in to receive SMS notifications from
              FortressFlow. You can reply STOP at any time to opt out.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950 px-4 py-8">
      <Card className="w-full max-w-lg dark:bg-gray-900 dark:border-gray-800">
        <CardHeader className="text-center pb-2">
          <div className="flex justify-center mb-3">
            <Shield className="w-12 h-12 text-blue-600 dark:text-blue-400" />
          </div>
          <CardTitle className="text-2xl dark:text-gray-100">
            FortressFlow
          </CardTitle>
          <p className="text-gray-500 dark:text-gray-400 text-sm mt-1">
            SMS Notification Consent
          </p>
        </CardHeader>

        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="bg-red-50 dark:bg-red-950 text-red-700 dark:text-red-400 text-sm p-3 rounded-lg">
                {error}
              </div>
            )}

            <div className="space-y-2">
              <label
                htmlFor="phone"
                className="text-sm font-medium text-gray-700 dark:text-gray-300"
              >
                Phone Number
              </label>
              <Input
                id="phone"
                type="tel"
                placeholder="+1 (555) 000-0000"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
                className="dark:bg-gray-800 dark:border-gray-700 dark:text-gray-100"
              />
            </div>

            <div className="flex items-start gap-3">
              <input
                id="consent"
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-gray-300 dark:border-gray-600 text-blue-600 focus:ring-blue-500 dark:bg-gray-800"
              />
              <label
                htmlFor="consent"
                className="text-sm text-gray-700 dark:text-gray-300 leading-relaxed"
              >
                I agree to receive SMS notifications from FortressFlow including
                appointment confirmations, follow-up reminders, and account
                notifications.
              </label>
            </div>

            <div className="rounded-lg bg-gray-100 dark:bg-gray-800 p-4 space-y-3 text-xs text-gray-600 dark:text-gray-400">
              <div className="flex items-start gap-2">
                <MessageSquare className="w-4 h-4 mt-0.5 shrink-0 text-blue-500" />
                <p>
                  Message frequency varies. Message and data rates may apply.
                </p>
              </div>
              <p>
                Reply <strong className="text-gray-800 dark:text-gray-200">STOP</strong> to
                cancel at any time. Reply{" "}
                <strong className="text-gray-800 dark:text-gray-200">HELP</strong> for help.
              </p>
              <p>
                By opting in, you consent to receive text messages from
                FortressFlow (Gengyve USA Inc.) at the phone number provided. Consent
                is not a condition of purchase.
              </p>
              <div className="flex gap-3 pt-1">
                <Link
                  href="/privacy"
                  className="text-blue-600 dark:text-blue-400 hover:underline"
                >
                  Privacy Policy
                </Link>
                <Link
                  href="/terms"
                  className="text-blue-600 dark:text-blue-400 hover:underline"
                >
                  Terms of Service
                </Link>
              </div>
            </div>

            <Button type="submit" className="w-full" disabled={loading || !agreed}>
              {loading ? "Submitting..." : "Opt In to SMS Notifications"}
            </Button>
          </form>

          <p className="mt-5 text-center text-xs text-gray-400 dark:text-gray-500">
            &copy; {new Date().getFullYear()} Gengyve USA Inc. All rights reserved.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
