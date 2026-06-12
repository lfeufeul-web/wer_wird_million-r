/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React from "react";
import { HelpCircle, Settings } from "lucide-react";

interface HeaderProps {
  activeTab: "explore" | "editor" | "community";
  setActiveTab: (tab: "explore" | "editor" | "community") => void;
  onPublish: () => void;
  questCount: number;
}

export default function Header({
  activeTab,
  setActiveTab,
  onPublish,
  questCount
}: HeaderProps) {
  return (
    <header className="bg-surface shadow-[0_1px_3px_0_rgba(0,0,0,0.05)] border-b border-outline-variant/30 sticky top-0 z-50 h-16 flex justify-between items-center px-6 w-full">
      <div className="flex items-center gap-8">
        <span className="font-display text-2xl font-extrabold text-primary tracking-tight select-none">
          QuestMapper
        </span>
        <nav className="hidden md:flex items-center gap-6">
          <button
            onClick={() => setActiveTab("explore")}
            className={`font-sans font-medium text-sm transition-all pb-1 cursor-pointer ${
              activeTab === "explore"
                ? "text-primary border-b-2 border-primary"
                : "text-on-surface-variant hover:text-primary"
            }`}
          >
            Explore
          </button>
          <button
            onClick={() => setActiveTab("editor")}
            className={`font-sans font-medium text-sm transition-all pb-1 cursor-pointer ${
              activeTab === "editor"
                ? "text-primary border-b-2 border-primary"
                : "text-on-surface-variant hover:text-primary"
            }`}
          >
            My Quests
          </button>
          <button
            onClick={() => setActiveTab("community")}
            className={`font-sans font-medium text-sm transition-all pb-1 cursor-pointer ${
              activeTab === "community"
                ? "text-primary border-b-2 border-primary"
                : "text-on-surface-variant hover:text-primary"
            }`}
          >
            Community
          </button>
        </nav>
      </div>

      <div className="flex items-center gap-4">
        {activeTab === "editor" && (
          <button
            id="publish-btn"
            onClick={onPublish}
            className="bg-primary text-on-primary font-display font-semibold text-sm px-5 py-2 rounded-full shadow-sm hover:bg-primary/95 transition-all scale-100 hover:scale-102 active:scale-95 btn-tactile cursor-pointer"
          >
            Publish Quiz
          </button>
        )}

        <div className="flex items-center gap-1.5 border-l border-outline-variant/40 pl-3 md:pl-4">
          <button
            title="Help Support"
            className="p-1.5 text-on-surface-variant hover:text-primary rounded-full hover:bg-surface-container transition-colors cursor-pointer"
          >
            <HelpCircle className="w-5 h-5" />
          </button>
          <button
            title="Map Settings"
            className="p-1.5 text-on-surface-variant hover:text-primary rounded-full hover:bg-surface-container transition-colors cursor-pointer"
          >
            <Settings className="w-5 h-5" />
          </button>

          <div
            className="w-9 h-9 rounded-full overflow-hidden border-2 border-outline-variant ml-2 flex-shrink-0 select-none shadow-sm hover:border-primary transition-all cursor-pointer"
            title="User Profile"
          >
            <img
              alt="User avatar"
              referrerPolicy="no-referrer"
              className="w-full h-full object-cover"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuD2GwvFoGsNzOPb9tx3DjjuW_IHfjvOVmAZ7iJW7wON_uFzzY9lSGzW4f_l9oto1lbLk4ej0mRqcMjrqkmYeO8mID8rKA1ADcH0BY943vLPu6ps-DMZaCVza9LEphoN4RKekDFw2aflfnjFvMuJC64z5x5lANUg4yfckJm6vi4B3enQOr3Hs3PwBxICEs196MjoS6BZ2lNFJrZ-G9gfuMtW8o2xe5g4V08hr3WD2S2e5foYH1_OWJ51LaETSzv5MHxkJXt7Y-cFmG93"
            />
          </div>
        </div>
      </div>
    </header>
  );
}
