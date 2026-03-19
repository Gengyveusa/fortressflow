"use client";

import { useState, useRef, useCallback } from "react";
import Link from "next/link";
import { Shield, Upload, FileText, CheckCircle, AlertCircle, ArrowLeft } from "lucide-react";
import Papa from "papaparse";
import { leadsApi } from "@/lib/api";

const REQUIRED_COLUMNS = ["email"];
const OPTIONAL_COLUMNS = ["first_name", "last_name", "company", "title", "phone", "source"];
const ALL_COLUMNS = [...REQUIRED_COLUMNS, ...OPTIONAL_COLUMNS];

interface ParsedRow {
  [key: string]: string;
}

export default function ImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ParsedRow[]>([]);
  const [headers, setHeaders] = useState<string[]>([]);
  const [columnMap, setColumnMap] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<"idle" | "parsing" | "ready" | "uploading" | "done" | "error">("idle");
  const [message, setMessage] = useState("");
  const dropRef = useRef<HTMLDivElement>(null);

  const parseFile = useCallback((f: File) => {
    setFile(f);
    setStatus("parsing");
    Papa.parse<ParsedRow>(f, {
      header: true,
      preview: 5,
      complete: (results) => {
        const cols = results.meta.fields ?? [];
        setHeaders(cols);
        setPreview(results.data);
        // Auto-map columns with matching names
        const map: Record<string, string> = {};
        ALL_COLUMNS.forEach((col) => {
          const match = cols.find((c) => c.toLowerCase().replace(/[\s-]/g, "_") === col);
          if (match) map[col] = match;
        });
        setColumnMap(map);
        setStatus("ready");
      },
      error: () => {
        setStatus("error");
        setMessage("Failed to parse CSV. Please check the file format.");
      },
    });
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const f = e.dataTransfer.files[0];
      if (f && f.name.endsWith(".csv")) parseFile(f);
    },
    [parseFile]
  );

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) parseFile(f);
  };

  const handleUpload = async () => {
    if (!file) return;
    setStatus("uploading");
    try {
      await leadsApi.import(file);
      setStatus("done");
      setMessage("Leads imported successfully!");
    } catch {
      setStatus("error");
      setMessage("Import failed. Please check the backend is running.");
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between max-w-7xl mx-auto">
          <div className="flex items-center gap-3">
            <Shield className="w-8 h-8 text-blue-600" />
            <span className="text-xl font-bold text-gray-900">FortressFlow</span>
          </div>
          <div className="flex items-center gap-6 text-sm font-medium text-gray-600">
            <Link href="/">Dashboard</Link>
            <Link href="/leads" className="text-blue-600">Leads</Link>
            <Link href="/sequences">Sequences</Link>
            <Link href="/compliance">Compliance</Link>
            <Link href="/analytics">Analytics</Link>
          </div>
        </div>
      </nav>

      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="mb-6">
          <Link href="/leads" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-4">
            <ArrowLeft className="w-4 h-4" />
            Back to Leads
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">Import Leads</h1>
          <p className="text-gray-500 mt-1">
            Upload a CSV file with verified professional contacts. Only
            legitimate B2B contacts should be imported.
          </p>
        </div>

        {/* Drop zone */}
        {status === "idle" || status === "parsing" ? (
          <div
            ref={dropRef}
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            className="border-2 border-dashed border-gray-300 rounded-xl p-12 text-center hover:border-blue-400 transition-colors bg-white"
          >
            <Upload className="w-12 h-12 mx-auto mb-4 text-gray-400" />
            <p className="text-lg font-medium text-gray-700 mb-2">
              Drop your CSV file here
            </p>
            <p className="text-sm text-gray-500 mb-4">
              Required: <code className="bg-gray-100 px-1 rounded">email</code>{" "}
              — Optional: first_name, last_name, company, title, phone, source
            </p>
            <label className="cursor-pointer bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium">
              Browse File
              <input
                type="file"
                accept=".csv"
                onChange={handleFileInput}
                className="hidden"
              />
            </label>
          </div>
        ) : null}

        {/* Column mapping */}
        {(status === "ready" || status === "uploading") && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm">
            <div className="p-4 border-b border-gray-200 flex items-center gap-3">
              <FileText className="w-5 h-5 text-blue-600" />
              <div>
                <p className="font-medium text-gray-900">{file?.name}</p>
                <p className="text-xs text-gray-500">
                  {preview.length} rows previewed
                </p>
              </div>
            </div>

            <div className="p-4">
              <h3 className="font-medium text-gray-900 mb-3">Column Mapping</h3>
              <div className="grid grid-cols-2 gap-3 mb-6">
                {ALL_COLUMNS.map((col) => (
                  <div key={col} className="flex items-center gap-3">
                    <span className="text-sm text-gray-600 w-28 shrink-0">
                      {col}
                      {col === "email" && (
                        <span className="text-red-500 ml-1">*</span>
                      )}
                    </span>
                    <select
                      value={columnMap[col] ?? ""}
                      onChange={(e) =>
                        setColumnMap((m) => ({ ...m, [col]: e.target.value }))
                      }
                      className="flex-1 border border-gray-200 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">— skip —</option>
                      {headers.map((h) => (
                        <option key={h} value={h}>
                          {h}
                        </option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>

              <h3 className="font-medium text-gray-900 mb-3">Preview (first 5 rows)</h3>
              <div className="overflow-x-auto rounded-lg border border-gray-200 mb-6">
                <table className="w-full text-xs">
                  <thead className="bg-gray-50">
                    <tr>
                      {headers.map((h) => (
                        <th key={h} className="text-left px-3 py-2 font-medium text-gray-600">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {preview.map((row, i) => (
                      <tr key={i} className="border-t border-gray-100">
                        {headers.map((h) => (
                          <td key={h} className="px-3 py-2 text-gray-700">
                            {row[h] ?? ""}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <button
                onClick={handleUpload}
                disabled={!columnMap["email"] || status === "uploading"}
                className="w-full bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {status === "uploading" ? "Uploading..." : "Import Leads"}
              </button>
            </div>
          </div>
        )}

        {status === "done" && (
          <div className="bg-white rounded-xl border border-green-200 p-6 text-center shadow-sm">
            <CheckCircle className="w-12 h-12 mx-auto mb-3 text-green-600" />
            <p className="text-lg font-medium text-gray-900">{message}</p>
            <Link
              href="/leads"
              className="mt-4 inline-block bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
            >
              View Leads
            </Link>
          </div>
        )}

        {status === "error" && (
          <div className="bg-white rounded-xl border border-red-200 p-6 text-center shadow-sm">
            <AlertCircle className="w-12 h-12 mx-auto mb-3 text-red-500" />
            <p className="text-lg font-medium text-gray-900">{message}</p>
            <button
              onClick={() => setStatus("idle")}
              className="mt-4 bg-gray-100 text-gray-700 px-6 py-2 rounded-lg hover:bg-gray-200 transition-colors text-sm font-medium"
            >
              Try Again
            </button>
          </div>
        )}
      </main>
    </div>
  );
}
