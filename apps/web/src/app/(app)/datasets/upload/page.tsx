"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useUploadFileDataset } from "@/features/connectors/hooks";
import { ApiError } from "@/lib/api-client";

const ACCEPTED_EXTENSIONS = ".csv,.tsv,.xlsx,.xls,.json,.ndjson,.parquet";

export default function UploadDatasetPage() {
  const router = useRouter();
  const upload = useUploadFileDataset();

  const [file, setFile] = React.useState<File | null>(null);
  const [datasetName, setDatasetName] = React.useState("");
  const [fileError, setFileError] = React.useState<string | null>(null);

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!file) {
      setFileError("Choose a file to upload");
      return;
    }
    setFileError(null);

    upload.mutate(
      { file, datasetName: datasetName.trim() || undefined },
      { onSuccess: (dataset) => router.push(`/datasets/${dataset.id}`) },
    );
  }

  const errorMessage =
    upload.error instanceof ApiError
      ? upload.error.message
      : upload.error
        ? "Something went wrong — please try again."
        : null;

  return (
    <div className="mx-auto max-w-lg">
      <Card>
        <CardHeader>
          <CardTitle>Upload a file</CardTitle>
          <CardDescription>CSV, TSV, Excel, JSON, or Parquet — parsed and ready to query immediately.</CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit} noValidate>
          <CardContent className="flex flex-col gap-4">
            {errorMessage && (
              <Alert variant="destructive">
                <AlertDescription>{errorMessage}</AlertDescription>
              </Alert>
            )}

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="file">File</Label>
              <Input
                id="file"
                type="file"
                accept={ACCEPTED_EXTENSIONS}
                onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              />
              {fileError && <p className="text-sm text-destructive">{fileError}</p>}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="datasetName">
                Dataset name <span className="text-muted-foreground">(optional)</span>
              </Label>
              <Input
                id="datasetName"
                value={datasetName}
                onChange={(event) => setDatasetName(event.target.value)}
                placeholder={file?.name ?? "Defaults to the filename"}
              />
            </div>

            <Button type="submit" disabled={upload.isPending} className="mt-2">
              {upload.isPending ? "Uploading…" : "Upload"}
            </Button>
          </CardContent>
        </form>
        <CardFooter className="justify-center text-sm text-muted-foreground">
          <Link href="/datasets" className="hover:underline">
            Back to datasets
          </Link>
        </CardFooter>
      </Card>
    </div>
  );
}
