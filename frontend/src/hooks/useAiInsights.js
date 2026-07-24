import { useMutation } from "@tanstack/react-query";
import api from "../lib/api.js";

export function useAiInsights() {
  return useMutation({
    mutationFn: async (period) => {
      const { data } = await api.get("/analytics/ai-insights/", {
        params: { period },
      });
      return data;
    },
  });
}
