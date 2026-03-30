"use client";

import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function MissionControlPage() {
  return (
    <div className="space-y-6 p-4">
      <h1 className="text-3xl font-bold text-gray-100">
        Mission Control
      </h1>
      <p className="text-gray-400">Real-time operations center</p>
      <div className="grid grid-cols-3 gap-4">
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader>
            <CardTitle className="text-gray-100">Live Operations</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant="default">10 Agents Active</Badge>
          </CardContent>
        </Card>
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader>
            <CardTitle className="text-gray-100">Data Provenance</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant="secondary">78% Enriched</Badge>
          </CardContent>
        </Card>
        <Card className="dark:bg-gray-900 dark:border-gray-800">
          <CardHeader>
            <CardTitle className="text-gray-100">Lead Journey</CardTitle>
          </CardHeader>
          <CardContent>
            <Badge variant="outline">1,247 Leads Tracked</Badge>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
