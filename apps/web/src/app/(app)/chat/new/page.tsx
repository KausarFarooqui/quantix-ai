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
import { useCreateConversation } from "@/features/chat/hooks";
import { useDatasets } from "@/features/connectors/hooks";
import { ApiError } from "@/lib/api-client";

export default function NewConversationPage() {
  const router = useRouter();
  const createConversation = useCreateConversation();
  const datasets = useDatasets();

  const [title, setTitle] = React.useState("");
  const [datasetId, setDatasetId] = React.useState("");
  const [titleError, setTitleError] = React.useState<string | null>(null);

  // Only datasets that have actually finished syncing are worth scoping a
  // conversation to — a pending/processing/failed one has no queryable
  // data yet for the agents to work against.
  const readyDatasets = (datasets.data ?? []).filter((dataset) => dataset.status === "ready");

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();

    if (title.trim().length === 0) {
      setTitleError("Required");
      return;
    }
    setTitleError(null);

    createConversation.mutate(
      { title: title.trim(), dataset_id: datasetId || null },
      { onSuccess: (conversation) => router.push(`/chat/${conversation.id}`) },
    );
  }

  const errorMessage =
    createConversation.error instanceof ApiError
      ? createConversation.error.message
      : createConversation.error
        ? "Something went wrong — please try again."
        : null;

  return (
    <div className="mx-auto max-w-lg">
      <Card>
        <CardHeader>
          <CardTitle>New conversation</CardTitle>
          <CardDescription>
            Ask questions about your data in plain language — the agent picks the right specialist for
            each turn.
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
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="e.g. Q3 revenue trends"
              />
              {titleError && <p className="text-sm text-destructive">{titleError}</p>}
            </div>

            <div className="flex flex-col gap-1.5">
              <Label htmlFor="dataset">
                Dataset <span className="text-muted-foreground">(optional)</span>
              </Label>
              <Select
                id="dataset"
                value={datasetId}
                onChange={(event) => setDatasetId(event.target.value)}
              >
                <option value="">No dataset — general conversation</option>
                {readyDatasets.map((dataset) => (
                  <option key={dataset.id} value={dataset.id}>
                    {dataset.name}
                  </option>
                ))}
              </Select>
              <p className="text-xs text-muted-foreground">
                Scoping to a dataset lets the agent query it directly instead of asking which one you
                mean.
              </p>
            </div>

            <Button type="submit" disabled={createConversation.isPending} className="mt-2">
              {createConversation.isPending ? "Creating…" : "Start conversation"}
            </Button>
          </CardContent>
        </form>
        <CardFooter className="justify-center text-sm text-muted-foreground">
          <Link href="/chat" className="hover:underline">
            Back to conversations
          </Link>
        </CardFooter>
      </Card>
    </div>
  );
}
