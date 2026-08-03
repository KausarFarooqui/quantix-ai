"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { chatApi } from "@/features/chat/api";
import type { ConversationCreateRequest, MessageResponse } from "@/types/api";

const conversationsKey = ["conversations"] as const;
const conversationKey = (id: string) => ["conversations", id] as const;
const messagesKey = (id: string) => ["conversations", id, "messages"] as const;
const agentRunsKey = (id: string) => ["conversations", id, "agent-runs"] as const;

export function useConversations() {
  return useQuery({ queryKey: conversationsKey, queryFn: chatApi.listConversations });
}

export function useConversation(id: string) {
  return useQuery({
    queryKey: conversationKey(id),
    queryFn: () => chatApi.getConversation(id),
    enabled: Boolean(id),
  });
}

export function useCreateConversation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ConversationCreateRequest) => chatApi.createConversation(body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: conversationsKey }),
  });
}

export function useMessages(conversationId: string) {
  return useQuery({
    queryKey: messagesKey(conversationId),
    queryFn: () => chatApi.listMessages(conversationId),
    enabled: Boolean(conversationId),
  });
}

let optimisticIdCounter = 0;

/**
 * `POST .../messages` runs the full LangGraph turn synchronously and can
 * take tens of seconds (no SSE streaming yet — see ADR-0004/ADR-0007), so
 * the composer would otherwise sit on an empty-looking thread the whole
 * time. The user's own message is appended to the cache the moment they
 * hit send; a failed request rolls that optimistic entry back rather than
 * leaving something in the thread that was never actually delivered.
 */
export function useSendMessage(conversationId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (content: string) => chatApi.sendMessage(conversationId, { content }),
    onMutate: async (content: string) => {
      await queryClient.cancelQueries({ queryKey: messagesKey(conversationId) });
      const previousMessages = queryClient.getQueryData<MessageResponse[]>(messagesKey(conversationId));
      const optimisticMessage: MessageResponse = {
        id: `optimistic-${++optimisticIdCounter}`,
        conversation_id: conversationId,
        role: "user",
        content,
        agent_type: null,
        created_at: new Date().toISOString(),
      };
      queryClient.setQueryData<MessageResponse[]>(messagesKey(conversationId), (old) => [
        ...(old ?? []),
        optimisticMessage,
      ]);
      return { previousMessages };
    },
    onError: (_error, _content, context) => {
      if (context?.previousMessages) {
        queryClient.setQueryData(messagesKey(conversationId), context.previousMessages);
      }
    },
    onSuccess: () => {
      // Refetch rather than append the response by hand: it also replaces
      // the optimistic user message with its real id, and keeps this in
      // sync with `useResyncDataset`'s "refetch, don't hand-patch" pattern
      // (see features/connectors/hooks.ts).
      queryClient.invalidateQueries({ queryKey: messagesKey(conversationId) });
      queryClient.invalidateQueries({ queryKey: agentRunsKey(conversationId) });
    },
  });
}

export function useAgentRuns(conversationId: string) {
  return useQuery({
    queryKey: agentRunsKey(conversationId),
    queryFn: () => chatApi.listAgentRuns(conversationId),
    enabled: Boolean(conversationId),
  });
}
