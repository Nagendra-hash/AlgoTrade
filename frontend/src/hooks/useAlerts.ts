// Alert + notification React Query hooks
// Path: frontend/src/hooks/useAlerts.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Alert, AlertListResponse, CreateAlertPayload, NotificationListResponse } from "@/types";

export function useAlerts(statusFilter?: string, symbol?: string) {
  return useQuery<AlertListResponse>({
    queryKey: ["alerts", statusFilter, symbol],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      if (symbol)       params.symbol = symbol;
      return (await api.get("/alerts", { params })).data;
    },
    staleTime: 30_000,
  });
}

export function useCreateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: CreateAlertPayload) =>
      api.post<Alert>("/alerts", data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useUpdateAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<CreateAlertPayload> }) =>
      api.put<Alert>(`/alerts/${id}`, data).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useDeleteAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/alerts/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function usePauseAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<Alert>(`/alerts/${id}/pause`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useResumeAlert() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post<Alert>(`/alerts/${id}/resume`).then((r) => r.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alerts"] }),
  });
}

export function useNotifications(isRead?: boolean) {
  return useQuery<NotificationListResponse>({
    queryKey: ["notifications", isRead],
    queryFn: async () => {
      const params: Record<string, string> = {};
      if (isRead !== undefined) params.is_read = String(isRead);
      return (await api.get("/notifications", { params })).data;
    },
    refetchInterval: 30_000,
    staleTime: 10_000,
  });
}

export function useUnreadCount() {
  return useQuery<{ unread: number }>({
    queryKey: ["notifications", "unread-count"],
    queryFn:  () => api.get("/notifications/unread-count").then((r) => r.data),
    refetchInterval: 15_000,
    staleTime: 5_000,
  });
}

export function useMarkNotificationsRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ids?: string[]) =>
      api.post("/notifications/read", { notification_ids: ids ?? null }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
}
