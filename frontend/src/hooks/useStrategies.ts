// Strategy hooks
// Path: frontend/src/hooks/useStrategies.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Strategy } from "@/types";

export function useStrategies() {
  return useQuery<Strategy[]>({
    queryKey: ["strategies"],
    queryFn:  () => api.get("/strategy").then((r) => r.data),
    staleTime: 30_000,
  });
}

export function useStrategy(id: string) {
  return useQuery<Strategy>({
    queryKey: ["strategy", id],
    queryFn:  () => api.get(`/strategy/${id}`).then((r) => r.data),
    enabled: Boolean(id),
  });
}

export function useGenerateStrategy() {
  return useMutation({
    mutationFn: (payload: { prompt: string; symbols: string[]; timeframe: string; ai_provider: string }) =>
      api.post("/strategy/generate", payload).then((r) => r.data),
  });
}

export function useGenerateAndSaveStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: { prompt: string; symbols: string[]; timeframe: string; ai_provider: string }) =>
      api.post<Strategy>("/strategy/generate-and-save", payload).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["strategies"] }),
  });
}

export function useDeployStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, mode }: { id: string; mode: "paper" | "live" }) =>
      api.post(`/strategy/${id}/deploy`, null, { params: { mode } }).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["strategies"] }),
  });
}

export function useDeleteStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/strategy/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["strategies"] }),
  });
}

export function useMarketplace(search?: string) {
  return useQuery<Strategy[]>({
    queryKey: ["marketplace", search],
    queryFn:  () => api.get("/strategy/marketplace", { params: search ? { search } : {} }).then((r) => r.data),
    staleTime: 60_000,
  });
}

export function useCloneStrategy() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<Strategy>(`/strategy/${id}/clone`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["strategies"] }),
  });
}
