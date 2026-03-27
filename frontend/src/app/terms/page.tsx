import Link from "next/link";
import { Shield, ArrowLeft } from "lucide-react";

export default function TermsOfServicePage() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950 py-12 px-4">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <Shield className="w-8 h-8 text-blue-600 dark:text-blue-400" />
          <span className="text-xl font-semibold dark:text-gray-100">
            FortressFlow
          </span>
        </div>

        <Link
          href="/sms-consent"
          className="inline-flex items-center gap-1 text-sm text-blue-600 dark:text-blue-400 hover:underline mb-6"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to SMS Consent
        </Link>

        <div className="prose prose-sm dark:prose-invert max-w-none space-y-6 text-gray-700 dark:text-gray-300">
          <h1 className="text-3xl font-bold dark:text-gray-100">
            Terms of Service
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Effective Date: March 27, 2026
          </p>

          <p>
            These Terms of Service (&quot;Terms&quot;) govern your access to and
            use of the FortressFlow platform operated by Gengyve USA Inc.
            (&quot;Company,&quot; &quot;we,&quot; &quot;us,&quot; or
            &quot;our&quot;). By using FortressFlow, you agree to these Terms.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            1. Acceptance of Terms
          </h2>
          <p>
            By accessing or using the FortressFlow platform, you agree to be
            bound by these Terms and our Privacy Policy. If you do not agree, you
            may not use the platform.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            2. Description of Service
          </h2>
          <p>
            FortressFlow is a compliance-first B2B lead generation and outreach
            platform. We provide tools for managing leads, building outreach
            sequences, tracking deliverability, and communicating with prospects
            via email and SMS.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            3. Account Registration
          </h2>
          <p>
            You must provide accurate and complete information when creating an
            account. You are responsible for maintaining the security of your
            account credentials and for all activity under your account.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            4. Acceptable Use
          </h2>
          <p>You agree not to:</p>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              Use the platform to send unsolicited messages in violation of
              applicable laws (CAN-SPAM, TCPA, GDPR, etc.).
            </li>
            <li>
              Upload or transmit malicious code, spam, or fraudulent content.
            </li>
            <li>
              Attempt to gain unauthorized access to the platform or its
              infrastructure.
            </li>
            <li>
              Violate any applicable local, state, national, or international
              law.
            </li>
            <li>
              Resell, sublicense, or distribute the platform without written
              consent.
            </li>
          </ul>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            5. SMS Communications
          </h2>
          <p>
            If you opt in to receive SMS notifications from FortressFlow, the
            following terms apply:
          </p>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              Message frequency varies based on your account activity and
              notification preferences.
            </li>
            <li>Message and data rates may apply.</li>
            <li>
              You may opt out at any time by replying <strong>STOP</strong> to
              any message.
            </li>
            <li>
              For help, reply <strong>HELP</strong> or contact us at{" "}
              <a
                href="mailto:thad@gengyveusa.com"
                className="text-blue-600 dark:text-blue-400 hover:underline"
              >
                thad@gengyveusa.com
              </a>
              .
            </li>
            <li>Consent to receive SMS is not a condition of purchase.</li>
          </ul>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            6. Intellectual Property
          </h2>
          <p>
            The FortressFlow platform, including its design, code, and content,
            is owned by Gengyve USA Inc. and protected by intellectual property
            laws. You retain ownership of data you upload to the platform.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            7. Payment and Billing
          </h2>
          <p>
            If you subscribe to a paid plan, you agree to pay all applicable fees
            as described at the time of purchase. Fees are non-refundable except
            as required by law. We may change pricing with 30 days&apos; advance
            notice.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            8. Limitation of Liability
          </h2>
          <p>
            To the maximum extent permitted by law, Gengyve USA Inc. shall not be
            liable for any indirect, incidental, special, consequential, or
            punitive damages, or any loss of profits or revenues, whether
            incurred directly or indirectly, arising from your use of the
            platform.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            9. Disclaimer of Warranties
          </h2>
          <p>
            The platform is provided &quot;as is&quot; and &quot;as
            available&quot; without warranties of any kind, whether express or
            implied, including implied warranties of merchantability, fitness for
            a particular purpose, and non-infringement.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            10. Termination
          </h2>
          <p>
            We may suspend or terminate your account at our discretion if you
            violate these Terms. Upon termination, your right to use the platform
            ceases immediately. You may request export of your data within 30
            days of termination.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            11. Governing Law
          </h2>
          <p>
            These Terms are governed by the laws of the State of California,
            without regard to conflict of law provisions. Any disputes arising
            from these Terms shall be resolved in the courts of San Francisco
            County, California.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            12. Changes to Terms
          </h2>
          <p>
            We may update these Terms from time to time. We will notify you of
            material changes by posting the updated Terms on this page with a
            revised effective date. Continued use of the platform constitutes
            acceptance of the updated Terms.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            13. Contact Us
          </h2>
          <p>
            If you have questions about these Terms of Service, contact us at:
          </p>
          <address className="not-italic">
            Gengyve USA Inc.
            <br />
            348 Stratford Drive
            <br />
            San Francisco, CA 94132
            <br />
            <a
              href="mailto:thad@gengyveusa.com"
              className="text-blue-600 dark:text-blue-400 hover:underline"
            >
              thad@gengyveusa.com
            </a>
          </address>
        </div>

        <div className="mt-12 pt-6 border-t border-gray-200 dark:border-gray-800 text-center text-xs text-gray-400 dark:text-gray-500">
          &copy; {new Date().getFullYear()} Gengyve USA Inc. All rights
          reserved.
        </div>
      </div>
    </div>
  );
}
