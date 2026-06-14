// Broker connection hooks
// Path: frontend/src/hooks/useBroker.ts
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export interface BrokerStatus {
  broker:         string;
  is_connected:   boolean;
  client_id?:     string;
  last_connected?: string;
  error_message?: string | null;
}

export function useBrokerStatus() {
  return useQuery<BrokerStatus[]>({
    queryKey: ["broker-status"],
    queryFn:  () => api.get("/brokers/status").then((r) => r.data),
    refetchInterval: 15_000,
    staleTime: 5_000,
  });
}
