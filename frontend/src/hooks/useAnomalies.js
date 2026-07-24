import { useQuery } from "@tanstack/react-query";
import api from "../lib/api.js";

export function useAnomalies({ organizationId, startDate, endDate, limit = 20 }) {
  return useQuery({
    queryKey: ["anomalies", organizationId, startDate, endDate, limit],
    queryFn: async () => {
      const { data } = await api.get("/analytics/anomalies/", {
        params: { start_date: startDate, end_date: endDate, limit },
      });
      return data;
    },
    enabled: Boolean(organizationId && startDate && endDate),
  });
}
