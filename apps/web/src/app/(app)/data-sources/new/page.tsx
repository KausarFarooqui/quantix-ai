"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useCreateDataSource } from "@/features/connectors/hooks";
import { CONNECTABLE_SOURCE_TYPE_LABELS, CONNECTOR_FIELDS } from "@/features/connectors/source-type-fields";
import { ApiError } from "@/lib/api-client";
import type { ConnectableSourceType } from "@/types/api";

const SOURCE_TYPES = Object.keys(CONNECTABLE_SOURCE_TYPE_LABELS) as ConnectableSourceType[];

export default function NewDataSourcePage() {
  const router = useRouter();
  const createDataSource = useCreateDataSource();

  const [name, setName] = React.useState("");
  const [sourceType, setSourceType] = React.useState<ConnectableSourceType>("postgresql");
  const [values, setValues] = React.useState<Record<string, string>>({});
  const [errors, setErrors] = React.useState<Record<string, string>>({});

  const fields = CONNECTOR_FIELDS[sourceType];

  function handleSourceTypeChange(next: ConnectableSourceType) {
    setSourceType(next);
    setValues({});
    setErrors({});
  }

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    const nextErrors: Record<string, string> = {};
    if (name.trim().length === 0) {
      nextErrors.name = "Required";
    }
    for (const field of fields) {
      if (field.required && !values[field.key]?.trim()) {
        nextErrors[field.key] = "Required";
      }
    }
    if (Object.keys(nextErrors).length > 0) {
      setErrors(nextErrors);
      return;
    }
    setErrors({});

    const config: Record<string, unknown> = {};
    const secrets: Record<string, unknown> = {};
    for (const field of fields) {
      const raw = values[field.key]?.trim();
      if (!raw) {
        continue;
      }
      const value = field.inputType === "number" ? Number(raw) : raw;
      (field.kind === "config" ? config : secrets)[field.key] = value;
    }

    createDataSource.mutate(
      {
        name: name.trim(),
        source_type: sourceType,
        config,
        secrets: Object.keys(secrets).length > 0 ? secrets : null,
      },
      { onSuccess: (dataSource) => router.push(`/data-sources/${dataSource.id}`) },
    );
  }

  const errorMessage =
    createDataSource.error instanceof ApiError
      ? createDataSource.error.message
      : createDataSource.error
        ? "Something went wrong — please try again."
        : null;

  return (
    <div className="mx-auto max-w-lg">
      <Card>
        <CardHeader>
          <CardTitle>Add a data source</CardTitle>
          <CardDescription>
            For CSV, Excel, JSON, or Parquet files, use{" "}
            <Link href="/datasets/upload" className="font-medium text-primary hover:underline">
              Upload a file
            </Link>{" "}
            instead — there&apos;s no connection to configure.
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit} noValidate>
          <CardContent className="flex flex-col gap-4">
            {errorMessage && (
              <Alert variant="destructive">
                <AlertDescription>{errorMessage}</AlertDescription>
              </Alert>
            )}

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Production Postgres"
              />
              {errors.name && <p className="text-sm text-destructive">{errors.name}</p>}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="sourceType">Type</Label>
              <Select
                id="sourceType"
                value={sourceType}
                onChange={(event) => handleSourceTypeChange(event.target.value as ConnectableSourceType)}
              >
                {SOURCE_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {CONNECTABLE_SOURCE_TYPE_LABELS[type]}
                  </option>
                ))}
              </Select>
            </div>

            {fields.map((field) => (
              <div key={field.key} className="flex flex-col gap-1.5">
                <Label htmlFor={field.key}>
                  {field.label}
                  {!field.required && <span className="text-muted-foreground"> (optional)</span>}
                </Label>
                {field.inputType === "textarea" ? (
                  <Textarea
                    id={field.key}
                    value={values[field.key] ?? ""}
                    onChange={(event) =>
                      setValues((prev) => ({ ...prev, [field.key]: event.target.value }))
                    }
                    placeholder={field.placeholder}
                    rows={6}
                  />
                ) : (
                  <Input
                    id={field.key}
                    type={field.inputType}
                    value={values[field.key] ?? ""}
                    onChange={(event) =>
                      setValues((prev) => ({ ...prev, [field.key]: event.target.value }))
                    }
                    placeholder={field.placeholder}
                    autoComplete={field.kind === "secret" ? "off" : undefined}
                  />
                )}
                {field.helpText && <p className="text-xs text-muted-foreground">{field.helpText}</p>}
                {errors[field.key] && <p className="text-sm text-destructive">{errors[field.key]}</p>}
              </div>
            ))}

            <Button type="submit" disabled={createDataSource.isPending} className="mt-2">
              {createDataSource.isPending ? "Adding…" : "Add data source"}
            </Button>
          </CardContent>
        </form>
        <CardFooter className="justify-center text-sm text-muted-foreground">
          <Link href="/data-sources" className="hover:underline">
            Back to data sources
          </Link>
        </CardFooter>
      </Card>
    </div>
  );
}
