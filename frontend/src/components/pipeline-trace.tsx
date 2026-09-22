/**
 * Horizontal pipeline trace: redacted -> classified -> scored -> retrieved
 * -> drafted -> routed. The one deliberate motion moment in this UI (per
 * the design spec) is meant to live here, tied to real state change, not
 * decoration: `active` stages get a pulse, everything else is static.
 */

export type TraceStage = {
  key: string;
  label: string;
  done: boolean;
  active?: boolean;
  detail?: string | null;
};

export function PipelineTrace({ stages }: { stages: TraceStage[] }) {
  return (
    <ol className="flex items-start">
      {stages.map((stage, i) => (
        <li key={stage.key} className="flex flex-1 items-start last:flex-none">
          <div className="flex flex-col items-start gap-1.5">
            <div className="flex items-center gap-2">
              <span
                aria-hidden
                data-state={stage.done ? "done" : stage.active ? "active" : "pending"}
                className="size-2.5 shrink-0 rounded-full bg-border data-[state=active]:animate-pulse data-[state=active]:bg-signal-medium data-[state=done]:bg-signal-low"
              />
              <span
                className={
                  "text-sm font-semibold " +
                  (stage.done || stage.active ? "text-foreground" : "text-muted-foreground")
                }
              >
                {stage.label}
              </span>
            </div>
            {stage.detail && (
              <span className="font-data text-xs text-muted-foreground">
                {stage.detail}
              </span>
            )}
          </div>
          {i < stages.length - 1 && (
            <div
              aria-hidden
              data-state={stage.done ? "done" : "pending"}
              className="mt-1 h-px flex-1 translate-y-[3px] bg-border data-[state=done]:bg-signal-low"
            />
          )}
        </li>
      ))}
    </ol>
  );
}
