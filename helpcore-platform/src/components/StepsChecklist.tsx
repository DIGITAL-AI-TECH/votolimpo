interface Step {
  order?: number;
  action: string;
  detail?: string;
}

interface StepsChecklistProps {
  steps: Step[];
}

export function StepsChecklist({ steps }: StepsChecklistProps) {
  if (!steps || steps.length === 0) return null;

  return (
    <ol className="space-y-2">
      {steps.map((step, i) => (
        <li key={i} className="flex gap-3 text-sm">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#FF5722]/20 text-xs font-bold text-[#FF5722]">
            {step.order ?? i + 1}
          </span>
          <div>
            <p className="font-medium text-white">{step.action}</p>
            {step.detail && (
              <p className="text-[#9EA5AC]">{step.detail}</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
