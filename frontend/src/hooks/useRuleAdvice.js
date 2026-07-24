import { useQuery } from "@tanstack/react-query";
import api from "../lib/api.js";

export function useRuleAdvice({ organizationId, startDate, endDate }) {
  return useQuery({
    queryKey: ["ruleAdvice", organizationId, startDate, endDate],
    queryFn: async () => {
      const { data } = await api.get("/analytics/rule-based-advice/", {
        params: { start_date: startDate, end_date: endDate },
      });
      return data;
    },
    enabled: Boolean(organizationId && startDate && endDate),
  });
}
