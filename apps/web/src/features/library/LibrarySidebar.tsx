// The library's sidebar (design 4.3): inbox, all papers, the collection tree and tags, each
// with its count. Papers dragged from the list drop onto a collection (filed) or a tag
// (tagged); a collection dragged onto another moves inside it, onto the heading to the top.
import {
  ChevronDown,
  ChevronRight,
  Folder,
  FolderOpen,
  Inbox,
  Library,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import { useState, type DragEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/query";
import { cn } from "@/lib/cn";

import {
  tagColors,
  useCollections,
  useCreateCollection,
  useCreateTag,
  useDeleteCollection,
  useDeleteTag,
  useFileInCollection,
  useLibraryPapers,
  useTagPapers,
  useTags,
  useUpdateCollection,
  useUpdateTag,
  type CollectionView,
  type PaperScope,
  type TagView,
} from "./api";
import { COLLECTION_TYPE, PAPERS_TYPE, carries, dragCollection, droppedPapers } from "./dnd";
import { useLibraryView } from "./store";

function sameScope(a: PaperScope, b: PaperScope) {
  return a.kind === b.kind && (a.id ?? null) === (b.id ?? null);
}

export function tagColorVar(color: string | null): string {
  return color && (tagColors as readonly string[]).includes(color)
    ? `var(--color-highlight-${color})`
    : "var(--color-text-muted)";
}

export function LibrarySidebar() {
  const { t } = useTranslation();
  const collections = useCollections();
  const all = useLibraryPapers({ kind: "all" });
  const [error, setError] = useState<string | null>(null);
  const inbox = collections.data?.find((c) => c.is_system);
  const userCollections = collections.data?.filter((c) => !c.is_system) ?? [];

  const report = (failure: unknown) => {
    const code = failure instanceof ApiError ? failure.code : "unknown";
    const params = failure instanceof ApiError ? failure.params : {};
    setError(t(`errors.${code}`, { ...params, defaultValue: t("errors.unknown") }));
  };

  return (
    <nav aria-label={t("library.sidebar")} className="space-y-4 p-2 text-ui">
      <div className="space-y-0.5">
        {inbox && (
          <ScopeItem
            scope={{ kind: "collection", id: inbox.id }}
            icon={<Inbox aria-hidden />}
            label={t("library.inbox")}
            count={inbox.paper_count}
            collectionId={inbox.id}
            onError={report}
          />
        )}
        <ScopeItem
          scope={{ kind: "all" }}
          icon={<Library aria-hidden />}
          label={t("library.allPapers")}
          count={all.data?.length}
          onError={report}
        />
      </div>
      {error && (
        <p role="alert" className="px-2 text-meta text-danger">
          {error}
        </p>
      )}
      <CollectionTree
        collections={userCollections}
        onError={(failure) => {
          report(failure);
        }}
      />
      <TagList onError={report} />
    </nav>
  );
}

function ScopeItem({
  scope,
  icon,
  label,
  count,
  depth = 0,
  collectionId,
  tagId,
  onError,
  actions,
  open,
  onToggleOpen,
  draggableCollection,
}: {
  scope: PaperScope;
  icon: ReactNode;
  label: ReactNode;
  count: number | undefined;
  depth?: number;
  /** Papers dropped here are filed in this collection. */
  collectionId?: string;
  /** Papers dropped here get this tag. */
  tagId?: string;
  onError: (failure: unknown) => void;
  actions?: ReactNode;
  open?: boolean;
  onToggleOpen?: () => void;
  /** Lets the row be dragged into another collection. */
  draggableCollection?: { id: string; onMoveHere: (movedId: string) => void };
}) {
  const { t } = useTranslation();
  const { scope: current, setScope } = useLibraryView();
  const file = useFileInCollection();
  const tag = useTagPapers();
  const [over, setOver] = useState(false);
  const active = sameScope(scope, current);

  const accepts = (event: DragEvent) =>
    (carries(event, PAPERS_TYPE) && (collectionId ?? tagId) !== undefined) ||
    (carries(event, COLLECTION_TYPE) && draggableCollection !== undefined);

  function drop(event: DragEvent) {
    setOver(false);
    if (!accepts(event)) return;
    event.preventDefault();
    if (carries(event, COLLECTION_TYPE) && draggableCollection) {
      const moved = event.dataTransfer.getData(COLLECTION_TYPE);
      if (moved && moved !== draggableCollection.id) draggableCollection.onMoveHere(moved);
      return;
    }
    const paperIds = droppedPapers(event);
    if (paperIds.length === 0) return;
    if (collectionId) file.mutate({ id: collectionId, paperIds }, { onError });
    else if (tagId) tag.mutate({ id: tagId, paperIds }, { onError });
  }

  return (
    <div
      className={cn(
        "group flex h-row items-center gap-1 rounded-md pr-1",
        active ? "bg-primary-soft text-fg" : "hover:bg-hovered",
        over && "outline-2 outline-primary",
      )}
      style={{ paddingLeft: `${String(4 + depth * 14)}px` }}
      draggable={draggableCollection !== undefined}
      onDragStart={(event) => {
        if (draggableCollection) dragCollection(event, draggableCollection.id);
      }}
      onDragOver={(event) => {
        if (!accepts(event)) return;
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => {
        setOver(false);
      }}
      onDrop={drop}
    >
      {onToggleOpen ? (
        <button
          type="button"
          className="grid size-4 place-items-center text-fg-muted"
          aria-label={open ? t("library.collapse") : t("library.expand")}
          aria-expanded={open}
          onClick={onToggleOpen}
        >
          {open ? <ChevronDown className="size-3.5" /> : <ChevronRight className="size-3.5" />}
        </button>
      ) : (
        <span className="w-4" />
      )}
      <button
        type="button"
        aria-current={active ? "page" : undefined}
        className="flex min-w-0 flex-1 items-center gap-2 text-left [&_svg]:size-4 [&_svg]:shrink-0 [&_svg]:text-fg-muted"
        onClick={() => {
          setScope(scope);
        }}
      >
        {icon}
        <span className="truncate">{label}</span>
      </button>
      <span className="hidden items-center group-focus-within:flex group-hover:flex">
        {actions}
      </span>
      {count !== undefined && (
        <span className="text-meta text-fg-muted tabular-nums">{count.toLocaleString()}</span>
      )}
    </div>
  );
}

function SectionHeading({
  title,
  addLabel,
  onAdd,
  onDropCollection,
}: {
  title: string;
  addLabel: string;
  onAdd: () => void;
  onDropCollection?: (collectionId: string) => void;
}) {
  const [over, setOver] = useState(false);
  return (
    <div
      className={cn(
        "flex items-center justify-between px-2 pb-1 text-meta font-medium tracking-wide text-fg-muted uppercase",
        over && "rounded-md outline-2 outline-primary",
      )}
      onDragOver={(event) => {
        if (!onDropCollection || !carries(event, COLLECTION_TYPE)) return;
        event.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => {
        setOver(false);
      }}
      onDrop={(event) => {
        setOver(false);
        if (!onDropCollection || !carries(event, COLLECTION_TYPE)) return;
        event.preventDefault();
        onDropCollection(event.dataTransfer.getData(COLLECTION_TYPE));
      }}
    >
      <h2>{title}</h2>
      <Button variant="ghost" size="icon" className="size-6" aria-label={addLabel} onClick={onAdd}>
        <Plus />
      </Button>
    </div>
  );
}

function NameForm({
  label,
  initial = "",
  onSubmit,
  onCancel,
}: {
  label: string;
  initial?: string;
  onSubmit: (name: string) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial);
  return (
    <form
      className="px-2 py-0.5"
      onSubmit={(event) => {
        event.preventDefault();
        if (name.trim()) onSubmit(name.trim());
      }}
    >
      <Input
        autoFocus
        aria-label={label}
        className="h-7"
        maxLength={200}
        value={name}
        onChange={(event) => {
          setName(event.target.value);
        }}
        onKeyDown={(event) => {
          if (event.key === "Escape") onCancel();
        }}
        onBlur={onCancel}
      />
    </form>
  );
}

function CollectionTree({
  collections,
  onError,
}: {
  collections: CollectionView[];
  onError: (failure: unknown) => void;
}) {
  const { t } = useTranslation();
  const create = useCreateCollection();
  const update = useUpdateCollection();
  const remove = useDeleteCollection();
  const { scope, setScope } = useLibraryView();
  // Which collection a new child is being typed under ("" for the top level).
  const [adding, setAdding] = useState<string | null>(null);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [closed, setClosed] = useState<ReadonlySet<string>>(new Set());
  const [deleting, setDeleting] = useState<CollectionView | null>(null);

  const children = (parent: string | null) => collections.filter((c) => c.parent_id === parent);
  const move = (id: string, parent: string | null) => {
    update.mutate({ id, parent_id: parent }, { onError });
  };

  function renderLevel(parent: string | null, depth: number): ReactNode {
    return children(parent).map((collection) => {
      const kids = children(collection.id);
      const open = !closed.has(collection.id);
      return (
        <div key={collection.id}>
          {renaming === collection.id ? (
            <NameForm
              label={t("library.renameCollection")}
              initial={collection.name}
              onCancel={() => {
                setRenaming(null);
              }}
              onSubmit={(name) => {
                setRenaming(null);
                update.mutate({ id: collection.id, name }, { onError });
              }}
            />
          ) : (
            <ScopeItem
              scope={{ kind: "collection", id: collection.id }}
              icon={open && kids.length > 0 ? <FolderOpen aria-hidden /> : <Folder aria-hidden />}
              label={collection.name}
              count={collection.paper_count}
              depth={depth}
              collectionId={collection.id}
              onError={onError}
              open={open}
              {...(kids.length > 0
                ? {
                    onToggleOpen: () => {
                      setClosed((current) => {
                        const next = new Set(current);
                        if (!next.delete(collection.id)) next.add(collection.id);
                        return next;
                      });
                    },
                  }
                : {})}
              draggableCollection={{
                id: collection.id,
                onMoveHere: (moved) => {
                  move(moved, collection.id);
                },
              }}
              actions={
                <>
                  <IconAction
                    label={t("library.newSubcollection", { name: collection.name })}
                    onClick={() => {
                      setAdding(collection.id);
                    }}
                  >
                    <Plus />
                  </IconAction>
                  <IconAction
                    label={t("library.renameNamed", { name: collection.name })}
                    onClick={() => {
                      setRenaming(collection.id);
                    }}
                  >
                    <Pencil />
                  </IconAction>
                  <IconAction
                    label={t("library.deleteNamed", { name: collection.name })}
                    onClick={() => {
                      setDeleting(collection);
                    }}
                  >
                    <Trash2 />
                  </IconAction>
                </>
              }
            />
          )}
          {adding === collection.id && (
            <div style={{ paddingLeft: `${String((depth + 1) * 14)}px` }}>
              <NameForm
                label={t("library.newCollectionName")}
                onCancel={() => {
                  setAdding(null);
                }}
                onSubmit={(name) => {
                  setAdding(null);
                  create.mutate({ name, parent_id: collection.id }, { onError });
                }}
              />
            </div>
          )}
          {open && renderLevel(collection.id, depth + 1)}
        </div>
      );
    });
  }

  return (
    <section>
      <SectionHeading
        title={t("library.collections")}
        addLabel={t("library.newCollection")}
        onAdd={() => {
          setAdding("");
        }}
        onDropCollection={(id) => {
          move(id, null);
        }}
      />
      <div className="space-y-0.5">{renderLevel(null, 0)}</div>
      {adding === "" && (
        <NameForm
          label={t("library.newCollectionName")}
          onCancel={() => {
            setAdding(null);
          }}
          onSubmit={(name) => {
            setAdding(null);
            create.mutate({ name, parent_id: null }, { onError });
          }}
        />
      )}
      {collections.length === 0 && adding === null && (
        <p className="px-2 text-meta text-fg-muted">{t("library.noCollections")}</p>
      )}
      <ConfirmDialog
        open={deleting !== null}
        title={t("library.deleteCollectionTitle", { name: deleting?.name ?? "" })}
        description={t("library.deleteCollectionText")}
        confirmLabel={t("library.delete")}
        cancelLabel={t("library.cancel")}
        onCancel={() => {
          setDeleting(null);
        }}
        onConfirm={() => {
          if (!deleting) return;
          const id = deleting.id;
          setDeleting(null);
          remove.mutate(id, {
            onError,
            onSuccess: () => {
              if (scope.kind === "collection" && scope.id === id) setScope({ kind: "all" });
            },
          });
        }}
      />
    </section>
  );
}

function IconAction({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Button
      variant="ghost"
      size="icon"
      className="size-6 [&_svg]:size-3.5"
      aria-label={label}
      title={label}
      onClick={onClick}
    >
      {children}
    </Button>
  );
}

function TagList({ onError }: { onError: (failure: unknown) => void }) {
  const { t } = useTranslation();
  const tags = useTags();
  const create = useCreateTag();
  const update = useUpdateTag();
  const remove = useDeleteTag();
  const { scope, setScope } = useLibraryView();
  const [adding, setAdding] = useState(false);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<TagView | null>(null);

  const nextColor = (count: number) => tagColors[count % tagColors.length] ?? null;

  return (
    <section>
      <SectionHeading
        title={t("library.tags")}
        addLabel={t("library.newTag")}
        onAdd={() => {
          setAdding(true);
        }}
      />
      <div className="space-y-0.5">
        {tags.data?.map((tag) =>
          renaming === tag.id ? (
            <NameForm
              key={tag.id}
              label={t("library.renameTag")}
              initial={tag.name}
              onCancel={() => {
                setRenaming(null);
              }}
              onSubmit={(name) => {
                setRenaming(null);
                update.mutate({ id: tag.id, name }, { onError });
              }}
            />
          ) : (
            <ScopeItem
              key={tag.id}
              scope={{ kind: "tag", id: tag.id }}
              icon={
                <span
                  aria-hidden
                  className="size-2.5 rounded-full"
                  style={{ backgroundColor: tagColorVar(tag.color) }}
                />
              }
              label={`#${tag.name}`}
              count={tag.paper_count}
              tagId={tag.id}
              onError={onError}
              actions={
                <>
                  <IconAction
                    label={t("library.recolorNamed", { name: tag.name })}
                    onClick={() => {
                      const index = tagColors.findIndex((color) => color === tag.color);
                      update.mutate(
                        { id: tag.id, color: tagColors[(index + 1) % tagColors.length] ?? null },
                        { onError },
                      );
                    }}
                  >
                    <span
                      className="size-3 rounded-full border border-line-strong"
                      style={{ backgroundColor: tagColorVar(tag.color) }}
                    />
                  </IconAction>
                  <IconAction
                    label={t("library.renameNamed", { name: tag.name })}
                    onClick={() => {
                      setRenaming(tag.id);
                    }}
                  >
                    <Pencil />
                  </IconAction>
                  <IconAction
                    label={t("library.deleteNamed", { name: tag.name })}
                    onClick={() => {
                      setDeleting(tag);
                    }}
                  >
                    <Trash2 />
                  </IconAction>
                </>
              }
            />
          ),
        )}
      </div>
      {adding && (
        <NameForm
          label={t("library.newTagName")}
          onCancel={() => {
            setAdding(false);
          }}
          onSubmit={(name) => {
            setAdding(false);
            create.mutate(
              { name: name.replace(/^#/, ""), color: nextColor(tags.data?.length ?? 0) },
              { onError },
            );
          }}
        />
      )}
      {tags.data?.length === 0 && !adding && (
        <p className="px-2 text-meta text-fg-muted">{t("library.noTags")}</p>
      )}
      <ConfirmDialog
        open={deleting !== null}
        title={t("library.deleteTagTitle", { name: deleting?.name ?? "" })}
        description={t("library.deleteTagText")}
        confirmLabel={t("library.delete")}
        cancelLabel={t("library.cancel")}
        onCancel={() => {
          setDeleting(null);
        }}
        onConfirm={() => {
          if (!deleting) return;
          const id = deleting.id;
          setDeleting(null);
          remove.mutate(id, {
            onError,
            onSuccess: () => {
              if (scope.kind === "tag" && scope.id === id) setScope({ kind: "all" });
            },
          });
        }}
      />
    </section>
  );
}
