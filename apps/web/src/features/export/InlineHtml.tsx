// A bibliography entry's inline HTML (Task 39: escaped text with <i>, <b>, <sup>, <sub> and a
// small-caps <span>) as React elements. Only those tags become elements; anything else is
// kept as its text, so nothing from a record's fields can inject markup.
import { Fragment, type ReactNode } from "react";

function render(node: Node, key: number): ReactNode {
  if (node.nodeType === Node.TEXT_NODE) return node.textContent;
  if (!(node instanceof Element)) return null;
  const children = Array.from(node.childNodes, render);
  switch (node.tagName.toLowerCase()) {
    case "i":
      return <i key={key}>{children}</i>;
    case "b":
      return <b key={key}>{children}</b>;
    case "sup":
      return <sup key={key}>{children}</sup>;
    case "sub":
      return <sub key={key}>{children}</sub>;
    case "span":
      if (node.getAttribute("style")?.includes("small-caps")) {
        return (
          <span key={key} className="[font-variant:small-caps]">
            {children}
          </span>
        );
      }
      return <Fragment key={key}>{children}</Fragment>;
    default:
      return <Fragment key={key}>{children}</Fragment>;
  }
}

export function InlineHtml({ html }: { html: string }) {
  const body = new DOMParser().parseFromString(`<body>${html}</body>`, "text/html").body;
  return <>{Array.from(body.childNodes, render)}</>;
}
