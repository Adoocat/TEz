// A record's screening state in colour, icon and words (never colour alone).
import { Ban, CircleCheck, CircleDashed, CircleHelp, CircleX } from "lucide-react";
import { useTranslation } from "react-i18next";

import { cn } from "@/lib/cn";

import type { RecordState } from "./queue";

const look: Record<RecordState, { icon: typeof CircleCheck; className: string }> = {
  undecided: { icon: CircleDashed, className: "text-fg-muted" },
  include: { icon: CircleCheck, className: "text-success" },
  exclude: { icon: CircleX, className: "text-danger" },
  maybe: { icon: CircleHelp, className: "text-warning" },
  not_retrieved: { icon: Ban, className: "text-fg-muted" },
};

export function StateBadge({ state, code }: { state: RecordState; code?: string | undefined }) {
  const { t } = useTranslation();
  const { icon: Icon, className } = look[state];
  return (
    <span className={cn("inline-flex items-center gap-1 text-meta", className)}>
      <Icon aria-hidden className="size-3.5" />
      {t(`screening.state.${state}`)}
      {code && <span className="font-mono">{code}</span>}
    </span>
  );
}
