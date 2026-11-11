// Drag-and-drop payloads inside the app. Custom types, so a drag from elsewhere (a file from
// the desktop) is never mistaken for papers or a collection.
import type { DragEvent } from "react";

export const PAPERS_TYPE = "application/x-tez-papers";
export const COLLECTION_TYPE = "application/x-tez-collection";

export function dragPapers(event: DragEvent, paperIds: string[]) {
  event.dataTransfer.setData(PAPERS_TYPE, JSON.stringify(paperIds));
  event.dataTransfer.effectAllowed = "copyMove";
}

export function dragCollection(event: DragEvent, collectionId: string) {
  event.dataTransfer.setData(COLLECTION_TYPE, collectionId);
  event.dataTransfer.effectAllowed = "move";
}

export function carries(event: DragEvent, type: string): boolean {
  return event.dataTransfer.types.includes(type);
}

export function droppedPapers(event: DragEvent): string[] {
  try {
    const value: unknown = JSON.parse(event.dataTransfer.getData(PAPERS_TYPE) || "[]");
    return Array.isArray(value) ? value.filter((id): id is string => typeof id === "string") : [];
  } catch {
    return [];
  }
}
