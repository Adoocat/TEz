// A note as it reads. react-markdown makes elements, never raw HTML, so a note cannot run code.
import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";

import { useBackend } from "@/app/backend";
import { cn } from "@/lib/cn";

import type { NoteLinkView } from "./api";
import { nameLinks, statusOf, type LinkType, type WrittenLink } from "./links";

const TEZ = /^tez:(note|paper|anchor|name)\/(.+)$/;

export function MarkdownPreview({
  text,
  links,
  onOpenLink,
}: {
  text: string;
  links: readonly NoteLinkView[];
  onOpenLink: (link: Pick<WrittenLink, "type" | "id" | "label">) => void;
}) {
  const { platform } = useBackend();
  return (
    <div className="note-prose">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        urlTransform={(url) => (TEZ.test(url) ? url : defaultUrlTransform(url))}
        components={{
          a: ({ href = "", children }) => {
            const found = TEZ.exec(href);
            if (!found) {
              return (
                <a
                  href={href}
                  onClick={(event) => {
                    event.preventDefault();
                    void platform.openExternal(href);
                  }}
                >
                  {children}
                </a>
              );
            }
            const [, type, target = ""] = found;
            const named = type === "name";
            const link = {
              type: named ? null : (type as LinkType),
              id: named ? null : target,
              label: named ? decodeURIComponent(target) : "",
            };
            const broken = statusOf(link, links)?.status === "broken";
            return (
              <a
                href="#"
                data-type={type}
                className={cn("note-chip", broken && "note-chip-broken")}
                onClick={(event) => {
                  event.preventDefault();
                  onOpenLink(link);
                }}
              >
                {children}
              </a>
            );
          },
          // Notes hold no pictures yet; an address in one must not load anything from the network.
          img: ({ alt }) => <span className="text-fg-muted">{alt}</span>,
        }}
      >
        {nameLinks(text)}
      </ReactMarkdown>
    </div>
  );
}
