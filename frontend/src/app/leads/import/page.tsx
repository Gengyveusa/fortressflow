"use client";

import { useState, useCallback, useRef } from "react";
import Link from "next/link";
import Papa from "papaparse";
import { Upload, ArrowLeft, FileSpreadsheet, Check, AlertCircle } from "lucide-react";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { leadsApi } from "@/lib/api";

const LEAD_FIELDS = [
  { key: "skip", label: "— Skip —" },
  { key: "email", label: "Email" },
  { key: "first_name", label: "First Name" },
  { key: "last_name", label: "Last Name" },
  { key: "company", label: "Company" },
  { key: "title", label: "Title" },
  { key: "phone", label: "Phone" },
  { key: "source", label: "Source" },
];

type ImportStatus = "idle" | "parsed" | "importing" | "success" | "error";

export default function LeadsImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [rows, setRows] = useState<string[][]>([]);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<ImportStatus>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const [importedCount, setImportedCount] = useState(0);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const parseFile = useCallback((f: File) => {
    setFile(f);
    setStatus("idle");
    setErrorMsg("");

    Papa.parse(f, {
      header: false,
      skipEmptyLines: true,
      complete(results) {
        const data = results.data as string[][];
        if (data.length < 2) {
          setErrorMsg("CSV must have a header row and at least one data row.");
          return;
        }
        const hdrs = data[0];
        setHeaders(hdrs);
        setRows(data.slice(1));

        // auto-map by header name similarity
        const autoMap: Record<string, string> = {};
        hdrs.forEach((h) => {
          const lower = h.toLowerCase().replace(/[^a-z]/g, "");
          const match = LEAD_FIELDS.find(
            (f) => f.key !== "skip" && f.key.replace("_", "").includes(lower)
          );
          if (match) autoMap[h] = match.key;
        });
        setMapping(autoMap);
        setStatus("parsed");
      },
      error() {
        setErrorMsg("Failed to parse CSV file.");
      },
    });
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const f = e.dataTransfer.files[0];
      if (f && f.name.endsWith(".csv")) parseFile(f);
      else setErrorMsg("Please upload a .csv file.");
    },
    [parseFile]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const f = e.target.files?.[0];
      if (f) parseFile(f);
    },
    [parseFile]
  );

  const handleImport = async () => {
    if (!file) return;
    setStatus("importing");
    setErrorMsg("");
    try {
      await leadsApi.import(file);
      setImportedCount(rows.length);
      setStatus("success");
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Import failed. Please try again.";
      setErrorMsg(message);
      setStatus("error");
    }
  };

  const previewRows = rows.slice(0, 5);

  return (
    <div className="space-y-4 max-w-4xl">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" asChild>
          <Link href="/leads">
            <ArrowLeft className="h-4 w-4 mr-1" /> Back to Leads
          </Link>
        </Button>
      </div>

      <h1 className="text-xl font-semibold">Import Leads</h1>

      {/* Success State */}
      {status === "success" && (
        <Card className="border-green-200 bg-green-50">
          <CardContent className="flex items-center gap-3 py-6">
            <Check className="h-6 w-6 text-green-600" />
            <div>
              <p className="font-medium text-green-800">
                Successfully imported {importedCount} leads!
              </p>
              <Link href="/leads" className="text-sm text-green-700 underline">
                View your leads →
              </Link>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error State */}
      {errorMsg && status !== "success" && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="flex items-center gap-3 py-4">
            <AlertCircle className="h-5 w-5 text-red-500 shrink-0" />
            <p className="text-sm text-red-700">{errorMsg}</p>
          </CardContent>
        </Card>
      )}

      {/* Upload Zone */}
      {status !== "success" && (
        <Card>
          <CardContent className="pt-6">
            <div
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              onClick={() => inputRef.current?.click()}
              className={`border-2 border-dashed rounded-lg p-10 text-center cursor-pointer transition-colors ${
                dragOver
                  ? "border-blue-400 bg-blue-50"
                  : "border-gray-300 hover:border-gray-400"
              }`}
            >
              <input
                ref={inputRef}
                type="file"
                accept=".csv"
                className="hidden"
                onChange={handleFileInput}
              />
              <Upload className="h-10 w-10 text-gray-400 mx-auto mb-3" />
              <p className="text-sm font-medium text-gray-600">
                Drag & drop a CSV file here, or click to browse
              </p>
              <p className="text-xs text-gray-400 mt-1">Supports .csv files</p>
              {file && (
                <Badge variant="secondary" className="mt-3">
                  <FileSpreadsheet className="h-3 w-3 mr-1" />
                  {file.name} ({rows.length} rows)
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Column Mapping */}
      {(status === "parsed" || status === "importing") && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Map Columns</CardTitle>
            <CardDescription>
              Match your CSV columns to lead fields.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {headers.map((h) => (
                <div key={h} className="flex items-center gap-3">
                  <span className="text-sm font-medium text-gray-700 w-32 truncate">
                    {h}
                  </span>
                  <Select
                    value={mapping[h] ?? "skip"}
                    onValueChange={(v) =>
                      setMapping((prev) => ({ ...prev, [h]: v }))
                    }
                  >
                    <SelectTrigger className="flex-1 h-9">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {LEAD_FIELDS.map((f) => (
                        <SelectItem key={f.key} value={f.key}>
                          {f.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Preview Table */}
      {(status === "parsed" || status === "importing") && previewRows.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Preview (first 5 rows)</CardTitle>
          </CardHeader>
          <CardContent className="p-0 overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  {headers.map((h) => (
                    <TableHead key={h} className="text-xs whitespace-nowrap">
                      {h}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {previewRows.map((row, i) => (
                  <TableRow key={i}>
                    {row.map((cell, j) => (
                      <TableCell key={j} className="text-xs whitespace-nowrap">
                        {cell}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
          <CardFooter className="justify-end gap-2 pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setFile(null);
                setHeaders([]);
                setRows([]);
                setMapping({});
                setStatus("idle");
              }}
            >
              Cancel
            </Button>
            <Button onClick={handleImport} disabled={status === "importing"}>
              {status === "importing" ? "Importing…" : `Import ${rows.length} Leads`}
            </Button>
          </CardFooter>
        </Card>
      )}
    </div>
  );
}
