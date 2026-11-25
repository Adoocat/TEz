import { useNavigate } from "react-router";

import { useLibraryView } from "@/features/library/store";

import { useAnchorAddress, type NoteLinkView } from "./api";
import { statusOf, type WrittenLink } from "./links";

/** Follow a link of a note: another note, a paper in the library, a place in the reader. */
export function useOpenLink(known: readonly NoteLinkView[] = []) {
  const navigate = useNavigate();
  const addressOf = useAnchorAddress();
  const selectPaper = useLibraryView((state) => state.selectPaper);
  return async (link: Pick<WrittenLink, "type" | "id" | "label">) => {
    const view = statusOf(link, known);
    const type = link.type ?? view?.target_type ?? null;
    const id = link.id ?? view?.target_id ?? null;
    // A name that names nothing yet goes nowhere.
    if (type === null || id === null) return;
    if (type === "note") await navigate(`/notes/${id}`);
    else if (type === "paper") {
      selectPaper(id);
      await navigate("/library");
    } else {
      await navigate(
        view?.anchor ? `/reader/${view.anchor.attachment_id}?anchor=${id}` : await addressOf(id),
      );
    }
  };
}
