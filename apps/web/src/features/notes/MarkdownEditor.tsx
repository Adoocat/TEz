// The Markdown editor: CodeMirror 6, links drawn as chips (raw while the cursor is in them) and
// suggestions after `[[`.
import {
  acceptCompletion,
  autocompletion,
  completionKeymap,
  type Completion,
  type CompletionContext,
} from "@codemirror/autocomplete";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { markdown } from "@codemirror/lang-markdown";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { EditorState, StateEffect, StateField, type Range } from "@codemirror/state";
import {
  Decoration,
  EditorView,
  keymap,
  placeholder as placeholderText,
  ViewPlugin,
  WidgetType,
  type DecorationSet,
  type ViewUpdate,
} from "@codemirror/view";
import { tags } from "@lezer/highlight";
import { useEffect, useRef } from "react";

import type { LinkSuggestion, NoteLinkView } from "./api";
import { linksIn, statusOf, writeLink, type WrittenLink } from "./links";

export interface EditorProps {
  initial: string;
  label: string;
  placeholder: string;
  newNoteLabel: (title: string) => string;
  /** What the saved note knows about its links: which are broken. */
  links: readonly NoteLinkView[];
  onChange: (text: string) => void;
  onOpenLink: (link: WrittenLink) => void;
  suggest: (query: string) => Promise<LinkSuggestion[]>;
  /** Makes a note for a name that is not there yet; its id. */
  createNote: (title: string) => Promise<string>;
}

const theme = EditorView.theme({
  "&": { height: "100%", color: "var(--color-text-primary)", backgroundColor: "transparent" },
  ".cm-scroller": { fontFamily: "var(--font-mono)", lineHeight: "1.65", overflow: "auto" },
  ".cm-content": { padding: "16px", caretColor: "var(--color-text-primary)" },
  "&.cm-focused": { outline: "none" },
  "&.cm-focused .cm-selectionBackground, .cm-selectionBackground": {
    backgroundColor: "color-mix(in srgb, var(--color-accent-default) 30%, transparent) !important",
  },
  ".cm-cursor": { borderLeftColor: "var(--color-text-primary)" },
  ".cm-placeholder": { color: "var(--color-text-muted)" },
  ".cm-tooltip": {
    backgroundColor: "var(--color-bg-raised)",
    color: "var(--color-text-primary)",
    border: "1px solid var(--color-border-subtle)",
    borderRadius: "6px",
  },
  ".cm-tooltip-autocomplete ul li[aria-selected]": {
    backgroundColor: "var(--color-accent-subtle)",
    color: "var(--color-text-primary)",
  },
});

const highlighting = HighlightStyle.define([
  { tag: tags.heading, fontWeight: "600" },
  { tag: tags.strong, fontWeight: "600" },
  { tag: tags.emphasis, fontStyle: "italic" },
  { tag: tags.quote, fontStyle: "italic", color: "var(--color-text-muted)" },
  { tag: [tags.processingInstruction, tags.url, tags.meta], color: "var(--color-text-muted)" },
]);

class ChipWidget extends WidgetType {
  constructor(
    readonly link: WrittenLink,
    readonly broken: boolean,
    readonly open: (link: WrittenLink) => void,
  ) {
    super();
  }
  override eq(other: ChipWidget) {
    return (
      other.link.label === this.link.label &&
      other.link.id === this.link.id &&
      other.broken === this.broken
    );
  }
  override toDOM() {
    const chip = document.createElement("a");
    chip.className = `note-chip${this.broken ? " note-chip-broken" : ""}`;
    chip.textContent = this.link.label;
    chip.dataset.type = this.link.type ?? "name";
    chip.href = "#";
    chip.addEventListener("click", (event) => {
      event.preventDefault();
      this.open(this.link);
    });
    return chip;
  }
  override ignoreEvent() {
    return true;
  }
}

const setLinks = StateEffect.define<readonly NoteLinkView[]>();
const knownLinks = StateField.define<readonly NoteLinkView[]>({
  create: () => [],
  update: (value, transaction) =>
    transaction.effects.reduce(
      (known, effect) => (effect.is(setLinks) ? effect.value : known),
      value,
    ),
});

function chips(open: (link: WrittenLink) => void) {
  const build = (view: EditorView): DecorationSet => {
    const known = view.state.field(knownLinks);
    const { selection } = view.state;
    const found: Range<Decoration>[] = [];
    for (const { from, to } of view.visibleRanges) {
      // Whole lines, so a link at an edge is seen whole.
      const start = view.state.doc.lineAt(from).from;
      const end = view.state.doc.lineAt(to).to;
      for (const link of linksIn(view.state.sliceDoc(start, end))) {
        const [a, b] = [start + link.from, start + link.to];
        const touched = selection.ranges.some((range) => range.from <= b && range.to >= a);
        if (touched && view.hasFocus) continue;
        const broken = statusOf(link, known)?.status === "broken";
        const widget = new ChipWidget(link, broken, open);
        found.push(Decoration.replace({ widget }).range(a, b));
      }
    }
    return Decoration.set(found, true);
  };
  return ViewPlugin.fromClass(
    class {
      decorations: DecorationSet;
      constructor(view: EditorView) {
        this.decorations = build(view);
      }
      update(update: ViewUpdate) {
        const told = update.transactions.some((t) => t.effects.some((e) => e.is(setLinks)));
        if (
          update.docChanged ||
          update.viewportChanged ||
          update.selectionSet ||
          update.focusChanged ||
          told
        ) {
          this.decorations = build(update.view);
        }
      }
    },
    { decorations: (plugin) => plugin.decorations },
  );
}

export function MarkdownEditor(props: EditorProps) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | null>(null);
  // The editor is made once; it calls what the props are now.
  const latest = useRef(props);
  useEffect(() => {
    latest.current = props;
  });

  useEffect(() => {
    if (!host.current) return;
    const complete = async (context: CompletionContext) => {
      const typed = context.matchBefore(/\[\[[^[\]\n]*/);
      if (!typed) return null;
      const query = typed.text.slice(2);
      const found = await latest.current.suggest(query);
      if (context.aborted) return null;
      const insert = (editor: EditorView, text: string, from: number, to: number) => {
        // A `]]` typed ahead belongs to the link.
        const end = editor.state.sliceDoc(to, to + 2) === "]]" ? to + 2 : to;
        editor.dispatch({
          changes: { from, to: end, insert: text },
          selection: { anchor: from + text.length },
        });
      };
      const options: Completion[] = found.map((suggestion) => ({
        label: suggestion.title,
        ...(suggestion.detail ? { detail: suggestion.detail } : {}),
        type: suggestion.target_type === "note" ? "text" : "class",
        apply: (editor, _, from, to) => {
          const words = suggestion.detail ?? suggestion.title;
          insert(editor, writeLink(words, suggestion.target_type, suggestion.target_id), from, to);
        },
      }));
      const title = query.trim();
      if (title !== "" && !found.some((s) => s.target_type === "note" && s.title === title)) {
        options.push({
          label: latest.current.newNoteLabel(title),
          type: "keyword",
          apply: (editor, _, from, to) => {
            insert(editor, `[[${title}]]`, from, to);
            void latest.current.createNote(title);
          },
        });
      }
      // The backend chose and ordered them (folded); CodeMirror's own filter would drop some.
      return { from: typed.from, options, filter: false };
    };
    const editor = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: latest.current.initial,
        extensions: [
          history(),
          markdown(),
          syntaxHighlighting(highlighting),
          theme,
          EditorView.lineWrapping,
          placeholderText(latest.current.placeholder),
          knownLinks.init(() => latest.current.links),
          chips((link) => {
            latest.current.onOpenLink(link);
          }),
          autocompletion({ override: [complete], icons: false, activateOnTyping: true }),
          keymap.of([
            { key: "Tab", run: acceptCompletion },
            ...completionKeymap,
            ...defaultKeymap,
            ...historyKeymap,
          ]),
          EditorView.contentAttributes.of({ "aria-label": latest.current.label }),
          EditorView.updateListener.of((update) => {
            if (update.docChanged) latest.current.onChange(update.state.doc.toString());
          }),
        ],
      }),
    });
    view.current = editor;
    return () => {
      editor.destroy();
      view.current = null;
    };
  }, []);

  useEffect(() => {
    view.current?.dispatch({ effects: setLinks.of(props.links) });
  }, [props.links]);

  return <div ref={host} className="h-full min-h-0" data-testid="note-editor" />;
}
