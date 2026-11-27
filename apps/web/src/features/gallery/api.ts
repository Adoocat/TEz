// Figures and tables kept from PDFs (Task 55).
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { components } from "@/api/schema";
import { useApi } from "@/app/backend";
import { unwrap, unwrapEmpty } from "@/lib/api/query";

export type AssetView = components["schemas"]["AssetView"];
export type AssetKind = AssetView["kind"];
export type AssetCreate = components["schemas"]["AssetCreate"];
export type AssetPatch = components["schemas"]["AssetPatch"];

const key = ["assets"] as const;

export function useAssets() {
  const api = useApi();
  return useQuery({
    queryKey: key,
    queryFn: async () => unwrap(await api.GET("/assets")),
  });
}

export function useAddAsset(attachmentId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (body: AssetCreate) =>
      unwrap(
        await api.POST("/attachments/{attachment_id}/assets", {
          params: { path: { attachment_id: attachmentId } },
          body,
        }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });
}

export function useUpdateAsset() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, patch }: { id: string; patch: AssetPatch }) =>
      unwrap(
        await api.PATCH("/assets/{asset_id}", { params: { path: { asset_id: id } }, body: patch }),
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });
}

export function useDeleteAsset() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      unwrapEmpty(await api.DELETE("/assets/{asset_id}", { params: { path: { asset_id: id } } }));
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });
}

/** The picture, fetched with the token (an <img> cannot send it), as a blob. */
export function useAssetBlob(assetId: string) {
  const api = useApi();
  return useQuery({
    queryKey: [...key, assetId, "image"],
    staleTime: Infinity,
    queryFn: async () => {
      return unwrap(
        await api.GET("/assets/{asset_id}/image", {
          params: { path: { asset_id: assetId } },
          parseAs: "blob",
        }),
      );
    },
  });
}

// One address per picture, made once: an address freed when a card unmounts would break the
// same picture shown elsewhere (the compare view), and pictures are small and few.
const addresses = new WeakMap<Blob, string>();

/** An address for the picture, for an <img>. */
export function useAssetUrl(assetId: string): string | null {
  const blob = useAssetBlob(assetId).data;
  if (!blob) return null;
  let url = addresses.get(blob);
  if (!url) {
    url = URL.createObjectURL(blob);
    addresses.set(blob, url);
  }
  return url;
}
