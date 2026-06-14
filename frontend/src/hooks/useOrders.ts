// Order hooks
// Path: frontend/src/hooks/useOrders.ts
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { Order, PlaceOrderPayload } from "@/types";

export function useOrders(symbol?: string) {
  return useQuery<Order[]>({
    queryKey: ["orders", symbol],
    queryFn:  () => api.get("/orders/", { params: symbol ? { symbol } : {} }).then((r) => r.data),
    staleTime: 15_000,
  });
}

export function usePlaceOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: PlaceOrderPayload) =>
      api.post<Order>("/orders/place", data).then((r) => r.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["portfolio-summary"] });
    },
  });
}

export function useCancelOrder() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete(`/orders/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["orders"] }),
  });
}
