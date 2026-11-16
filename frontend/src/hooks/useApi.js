import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";
export function useApi(path, interval) {
  return useQuery({
    queryKey: [path],
    queryFn: ({ signal }) => api(path, { signal }),
    enabled: path !== null,
    refetchInterval: interval,
  });
}
