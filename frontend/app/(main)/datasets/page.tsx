"use client";

import { useState } from "react";
import { Upload, FileText, CheckCircle, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  status: "uploading" | "complete" | "error";
  progress: number;
}

export default function DatasetUploadPage() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [datasetName, setDatasetName] = useState("");

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files;
    if (!selected) return;

    const newFiles = Array.from(selected).map((file) => ({
      id: Math.random().toString(36),
      name: file.name,
      size: file.size,
      status: "uploading" as const,
      progress: 0,
    }));

    setFiles((prev) => [...prev, ...newFiles]);

    newFiles.forEach((file) => {
      let progress = 0;
      const interval = setInterval(() => {
        progress += Math.random() * 10;
        if (progress >= 100) {
          progress = 100;
          clearInterval(interval);
          setFiles((prev) =>
            prev.map((f) =>
              f.id === file.id
                ? { ...f, progress: 100, status: "complete" }
                : f,
            ),
          );
        } else {
          setFiles((prev) =>
            prev.map((f) => (f.id === file.id ? { ...f, progress: Math.round(progress) } : f)),
          );
        }
      }, 200);
    });
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "complete": return <CheckCircle className="h-5 w-5 text-green-500" />;
      case "error": return <AlertCircle className="h-5 w-5 text-red-500" />;
      default: return <Upload className="h-5 w-5 text-blue-500 animate-bounce" />;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Dataset Upload</h1>
        <p className="text-muted-foreground">Upload evaluation datasets for your runs</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Upload Dataset</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="dataset-name">Dataset Name</Label>
            <Input
              id="dataset-name"
              value={datasetName}
              onChange={(e) => setDatasetName(e.target.value)}
              placeholder="E.g., Customer Support Q&A"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="file-upload">Dataset File (JSON/CSV)</Label>
            <div className="border-2 border-dashed rounded-md p-6 text-center">
              <FileText className="mx-auto h-12 w-12 text-muted-foreground" />
              <Input
                id="file-upload"
                type="file"
                accept=".json,.csv,.jsonl"
                onChange={handleFileChange}
                className="mt-2"
              />
              <p className="text-sm text-muted-foreground mt-2">
                Drag and drop or click to upload. Supports JSON, CSV, and JSONL.
              </p>
            </div>
          </div>

          {files.length > 0 && (
            <div className="space-y-3">
              {files.map((file) => (
                <div key={file.id} className="flex items-center gap-3 rounded-md border p-3">
                  {getStatusIcon(file.status)}
                  <div className="flex-1">
                    <p className="font-medium">{file.name}</p>
                    <p className="text-sm text-muted-foreground">{formatSize(file.size)}</p>
                    <div className="mt-1 h-1.5 w-full rounded-full bg-muted">
                      <div
                        className="h-1.5 rounded-full bg-primary transition-all"
                        style={{ width: `${file.progress}%` }}
                      />
                    </div>
                  </div>
                  <Badge variant={file.status === "complete" ? "default" : "secondary"}>
                    {file.status}
                  </Badge>
                </div>
              ))}
            </div>
          )}

          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline">Cancel</Button>
            <Button disabled={files.length === 0 || files.some((f) => f.status !== "complete")}>
              Create Dataset
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
