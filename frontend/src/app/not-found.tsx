import Link from "next/link";
import { Shield } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-950">
      <div className="text-center space-y-6 px-4">
        <div className="flex justify-center">
          <Shield className="w-16 h-16 text-blue-600 dark:text-blue-400" />
        </div>
        <div>
          <h1 className="text-6xl font-bold text-gray-900 dark:text-gray-100">
            404
          </h1>
          <p className="mt-2 text-lg text-gray-600 dark:text-gray-400">
            Page not found
          </p>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-500">
            The page you&apos;re looking for doesn&apos;t exist or has been
            moved.
          </p>
        </div>
        <Link href="/">
          <Button>Back to Dashboard</Button>
        </Link>
      </div>
    </div>
  );
}
