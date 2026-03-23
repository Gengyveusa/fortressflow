"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import type { QuestionData, QuestionItem, QuestionOption } from "./types";

function OptionButton({
  option,
  selected,
  onClick,
}: {
  option: QuestionOption;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
        "border",
        selected
          ? "bg-blue-600 text-white border-blue-600 dark:bg-blue-500 dark:border-blue-500"
          : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-600 hover:border-blue-400 dark:hover:border-blue-500 hover:bg-blue-50 dark:hover:bg-blue-950/30"
      )}
    >
      {option.icon && <span className="mr-1">{option.icon}</span>}
      {option.label}
    </button>
  );
}

function QuestionRow({
  item,
  onAnswer,
}: {
  item: QuestionItem;
  onAnswer: (value: string) => void;
}) {
  const [selected, setSelected] = useState<string | null>(null);

  const handleClick = (option: QuestionOption) => {
    setSelected(option.value);
    onAnswer(option.value);
  };

  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-gray-700 dark:text-gray-300">
        {item.question}
      </p>
      <div className="flex flex-wrap gap-1.5">
        {item.options.map((opt) => (
          <OptionButton
            key={opt.value}
            option={opt}
            selected={selected === opt.value}
            onClick={() => handleClick(opt)}
          />
        ))}
      </div>
    </div>
  );
}

interface QuestionCardProps {
  data: QuestionData;
  onAnswer: (answer: string) => void;
}

export function QuestionCard({ data, onAnswer }: QuestionCardProps) {
  return (
    <div className="rounded-xl border border-purple-200 dark:border-purple-800 bg-purple-50/50 dark:bg-purple-950/20 overflow-hidden">
      <div className="px-3 py-2.5 space-y-3">
        {data.questions.map((q, i) => (
          <QuestionRow
            key={i}
            item={q}
            onAnswer={(value) => onAnswer(`${q.question} ${value}`)}
          />
        ))}
      </div>
    </div>
  );
}
