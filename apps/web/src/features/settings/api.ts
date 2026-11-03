import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap, unwrapEmpty } from "@/lib/api/query";

export type AppSettings = components["schemas"]["AppSettings"];
export type SettingsPatch = components["schemas"]["SettingsPatch"];
export type SecretName = components["schemas"]["SecretName"];

export const settingsKey = ["settings"] as const;
const secretsKey = ["secrets"] as const;

export function useSettings() {
  const api = useApi();
  return useQuery({
    queryKey: settingsKey,
    queryFn: async () => unwrap(await api.GET("/settings")),
  });
}

export function useUpdateSettings() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (patch: SettingsPatch) =>
      unwrap(await api.PATCH("/settings", { body: patch })),
    onSuccess: (settings) => {
      queryClient.setQueryData(settingsKey, settings);
    },
  });
}

export function useSecrets() {
  const api = useApi();
  return useQuery({
    queryKey: secretsKey,
    queryFn: async () => unwrap(await api.GET("/secrets")),
  });
}

export function useSetSecret() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ name, value }: { name: SecretName; value: string }) => {
      unwrapEmpty(
        await api.PUT("/secrets/{name}", { params: { path: { name } }, body: { value } }),
      );
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: secretsKey }),
  });
}

export function useDeleteSecret() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (name: SecretName) => {
      unwrapEmpty(await api.DELETE("/secrets/{name}", { params: { path: { name } } }));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: secretsKey }),
  });
}

export function useLibraryInfo() {
  const api = useApi();
  return useQuery({
    queryKey: ["library"],
    queryFn: async () => unwrap(await api.GET("/library")),
  });
}
