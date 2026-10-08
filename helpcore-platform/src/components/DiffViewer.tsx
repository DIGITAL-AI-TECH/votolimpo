"use client";

import { useState } from "react";
import ReactDiffViewer, { DiffMethod } from "react-diff-viewer-continued";

interface DiffViewerProps {
  oldValue: string;
  newValue: string;
  oldTitle?: string;
  newTitle?: string;
}

export function DiffViewer({
  oldValue,
  newValue,
  oldTitle = "Original",
  newTitle = "Reescrita LLM",
}: DiffViewerProps) {
  const [splitView, setSplitView] = useState(true);

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <button
          onClick={() => setSplitView(true)}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
            splitView
              ? "bg-[#FF5722] text-white"
              : "border border-[#1F1F1F] text-[#9EA5AC] hover:text-white"
          }`}
        >
          Side by Side
        </button>
        <button
          onClick={() => setSplitView(false)}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
            !splitView
              ? "bg-[#FF5722] text-white"
              : "border border-[#1F1F1F] text-[#9EA5AC] hover:text-white"
          }`}
        >
          Inline
        </button>
      </div>
      <div className="overflow-x-auto rounded-xl border border-[#1F1F1F]">
        <ReactDiffViewer
          oldValue={oldValue}
          newValue={newValue}
          splitView={splitView}
          compareMethod={DiffMethod.WORDS}
          leftTitle={oldTitle}
          rightTitle={newTitle}
          useDarkTheme
          styles={{
            variables: {
              dark: {
                diffViewerBackground: "#151515",
                diffViewerColor: "#D4D8DD",
                addedBackground: "#1a3a1a",
                addedColor: "#4ade80",
                removedBackground: "#3a1a1a",
                removedColor: "#f87171",
                wordAddedBackground: "#22543d",
                wordRemovedBackground: "#742a2a",
                addedGutterBackground: "#1a3a1a",
                removedGutterBackground: "#3a1a1a",
                gutterBackground: "#0a0a0a",
                gutterColor: "#9EA5AC",
                codeFoldBackground: "#1A1A1A",
                codeFoldGutterBackground: "#1A1A1A",
                codeFoldContentColor: "#9EA5AC",
                emptyLineBackground: "#151515",
              },
            },
            contentText: {
              fontSize: "13px",
              lineHeight: "1.6",
              fontFamily: "'Nunito Sans', system-ui, sans-serif",
            },
          }}
        />
      </div>
    </div>
  );
}
