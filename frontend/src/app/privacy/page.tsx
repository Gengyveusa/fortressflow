import Link from "next/link";
import { Shield, ArrowLeft } from "lucide-react";

export default function PrivacyPolicyPage() {
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
            Privacy Policy
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Effective Date: March 27, 2026
          </p>

          <p>
            Gengyve USA Inc. (&quot;Company,&quot; &quot;we,&quot; &quot;us,&quot;
            or &quot;our&quot;) operates the FortressFlow platform. This Privacy
            Policy explains how we collect, use, disclose, and safeguard your
            information when you use our services.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            1. Information We Collect
          </h2>
          <p>We may collect the following categories of information:</p>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              <strong>Account Information:</strong> name, email address, company
              name, and phone number provided during registration.
            </li>
            <li>
              <strong>Usage Data:</strong> IP address, browser type, pages
              visited, and actions taken within the platform.
            </li>
            <li>
              <strong>Communications:</strong> phone numbers and consent records
              for SMS notifications, email correspondence, and support requests.
            </li>
            <li>
              <strong>Business Data:</strong> leads, sequences, templates, and
              other content you create within the platform.
            </li>
          </ul>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            2. How We Use Your Information
          </h2>
          <ul className="list-disc pl-6 space-y-1">
            <li>Provide, operate, and maintain the FortressFlow platform.</li>
            <li>
              Send transactional and notification SMS messages to numbers that
              have provided consent.
            </li>
            <li>
              Improve our services, develop new features, and analyze usage
              trends.
            </li>
            <li>
              Communicate with you about your account, support inquiries, and
              service updates.
            </li>
            <li>Comply with legal obligations and enforce our terms.</li>
          </ul>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            3. SMS Communications
          </h2>
          <p>
            If you opt in to receive SMS notifications, we will send text
            messages to the phone number you provide. Message frequency varies.
            Message and data rates may apply. You may opt out at any time by
            replying <strong>STOP</strong> to any message. Reply{" "}
            <strong>HELP</strong> for assistance. Consent to receive SMS is not a
            condition of purchase.
          </p>
          <p>
            We do not share your phone number or SMS consent data with third
            parties for their marketing purposes.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            4. Data Sharing and Disclosure
          </h2>
          <p>
            We do not sell your personal information. We may share information
            with:
          </p>
          <ul className="list-disc pl-6 space-y-1">
            <li>
              <strong>Service Providers:</strong> third-party vendors who help us
              operate the platform (e.g., hosting, SMS delivery, analytics).
            </li>
            <li>
              <strong>Legal Requirements:</strong> when required by law,
              regulation, or legal process.
            </li>
            <li>
              <strong>Business Transfers:</strong> in connection with a merger,
              acquisition, or sale of assets.
            </li>
          </ul>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            5. Data Security
          </h2>
          <p>
            We implement industry-standard security measures to protect your
            data, including encryption in transit and at rest, access controls,
            and regular security assessments. However, no method of transmission
            or storage is 100% secure.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            6. Data Retention
          </h2>
          <p>
            We retain your information for as long as your account is active or
            as needed to provide services. We retain SMS consent records for a
            minimum of five years to comply with regulatory requirements. You may
            request deletion of your account data by contacting us.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            7. Your Rights
          </h2>
          <p>
            Depending on your jurisdiction, you may have rights to access,
            correct, delete, or port your personal data. To exercise these
            rights, contact us at{" "}
            <a
              href="mailto:thad@gengyveusa.com"
              className="text-blue-600 dark:text-blue-400 hover:underline"
            >
              thad@gengyveusa.com
            </a>
            .
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            8. Changes to This Policy
          </h2>
          <p>
            We may update this Privacy Policy from time to time. We will notify
            you of material changes by posting the updated policy on this page
            with a revised effective date.
          </p>

          <h2 className="text-xl font-semibold dark:text-gray-100">
            9. Contact Us
          </h2>
          <p>
            If you have questions about this Privacy Policy, contact us at:
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
