"use client";

import { useState, useCallback } from "react";
import { FileText, Trash2, Eye, Download } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

interface ParsedRow {
  [key: string]: unknown;
}

interface DatasetFile {
  name: string;
  size: number;
  rowCount: number;
  columns: string[];
  rows: ParsedRow[];
}

function parseCSV(text: string): ParsedRow[] {
  const lines = text.trim().split("\n");
  if (lines.length < 2) return [];
  const headerLine = lines[0];
  if (!headerLine) return [];
  const headers = headerLine.split(",").map((h) => h.trim().replace(/^"|"$/g, ""));
  return lines.slice(1).map((line) => {
    const values = line.split(",").map((v) => v.trim().replace(/^"|"$/g, ""));
    const row: ParsedRow = {};
    headers.forEach((h, i) => {
      row[h] = values[i] ?? "";
    });
    return row;
  });
}

function parseJSON(text: string): ParsedRow[] {
  const data = JSON.parse(text);
  if (Array.isArray(data)) return data;
  if (data.items && Array.isArray(data.items)) return data.items;
  if (data.data && Array.isArray(data.data)) return data.data;
  return [data];
}

function parseJSONL(text: string): ParsedRow[] {
  return text
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

const formatSize = (bytes: number) => {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};

export default function DatasetsPage() {
  const [dataset, setDataset] = useState<DatasetFile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [previewRows, setPreviewRows] = useState(10);

  const handleFile = useCallback((file: File) => {
    setError(null);
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const text = e.target?.result as string;
        let rows: ParsedRow[];
        if (file.name.endsWith(".csv")) {
          rows = parseCSV(text);
        } else if (file.name.endsWith(".jsonl")) {
          rows = parseJSONL(text);
        } else {
          rows = parseJSON(text);
        }
        if (rows.length === 0) {
          setError("No data rows found in file.");
          return;
        }
        const columns = [...new Set(rows.flatMap((r) => Object.keys(r)))];
        setDataset({
          name: file.name,
          size: file.size,
          rowCount: rows.length,
          columns,
          rows,
        });
      } catch (err) {
        setError(`Failed to parse file: ${err instanceof Error ? err.message : "Unknown error"}`);
      }
    };
    reader.readAsText(file);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const downloadJSON = () => {
    if (!dataset) return;
    const blob = new Blob([JSON.stringify(dataset.rows, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = dataset.name.replace(/\.[^.]+$/, "") + ".json";
    a.click();
    URL.revokeObjectURL(url);
  };

  const clearDataset = () => {
    setDataset(null);
    setError(null);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Datasets</h1>
        <p className="text-muted-foreground">
          Upload and preview evaluation datasets. Parse JSON, CSV, and JSONL files.
        </p>
      </div>

      {!dataset ? (
        <Card>
          <CardHeader>
            <CardTitle>Upload Dataset</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Dataset File</Label>
              <div
                className="cursor-pointer rounded-md border-2 border-dashed p-8 text-center transition-colors hover:border-primary/50"
                onDragOver={(e) => e.preventDefault()}
                onDrop={handleDrop}
                onClick={() => document.getElementById("file-upload")?.click()}
              >
                <FileText className="mx-auto h-12 w-12 text-muted-foreground" />
                <p className="mt-2 text-sm text-muted-foreground">
                  Drag and drop or click to upload
                </p>
                <p className="mt-1 text-xs text-muted-foreground">Supports JSON, CSV, and JSONL</p>
                <Input
                  id="file-upload"
                  type="file"
                  accept=".json,.csv,.jsonl"
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) handleFile(file);
                  }}
                />
              </div>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
          </CardContent>
        </Card>
      ) : (
        <>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  {dataset.name}
                  <Badge variant="secondary">{dataset.rowCount} rows</Badge>
                </CardTitle>
                <div className="flex items-center gap-2">
                  <Button variant="outline" size="sm" onClick={downloadJSON}>
                    <Download className="mr-1 h-4 w-4" />
                    Export JSON
                  </Button>
                  <Button variant="outline" size="sm" onClick={clearDataset}>
                    <Trash2 className="mr-1 h-4 w-4" />
                    Clear
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="mb-4 flex items-center gap-4 text-sm text-muted-foreground">
                <span>{formatSize(dataset.size)}</span>
                <span>{dataset.columns.length} columns</span>
                <span>{dataset.rowCount} rows</span>
              </div>
              <div className="flex flex-wrap gap-1">
                {dataset.columns.map((col) => (
                  <Badge key={col} variant="outline">
                    {col}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <Eye className="h-4 w-4" />
                  Preview
                </CardTitle>
                <div className="flex items-center gap-2">
                  <Label className="text-sm text-muted-foreground">Rows:</Label>
                  <Input
                    type="number"
                    value={previewRows}
                    onChange={(e) => setPreviewRows(Math.max(1, parseInt(e.target.value) || 10))}
                    className="w-20"
                    min="1"
                    max={dataset.rowCount}
                  />
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="p-2 text-left font-medium text-muted-foreground">#</th>
                      {dataset.columns.map((col) => (
                        <th key={col} className="p-2 text-left font-medium text-muted-foreground">
                          {col}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {dataset.rows.slice(0, previewRows).map((row, i) => (
                      <tr key={i} className="border-b last:border-0">
                        <td className="p-2 text-muted-foreground">{i + 1}</td>
                        {dataset.columns.map((col) => (
                          <td key={col} className="max-w-[300px] truncate p-2">
                            {String(row[col] ?? "")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
