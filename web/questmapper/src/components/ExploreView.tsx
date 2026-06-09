/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from "react";
import { Compass, Play, Edit3, Heart, MapPin, Gamepad2, Search } from "lucide-react";
import { Quest, MapTemplate } from "../types";
import { MAP_TEMPLATES } from "../data";

interface ExploreViewProps {
  quests: Quest[];
  onSelectQuest: (quest: Quest) => void;
  onPlayQuest: (quest: Quest) => void;
  onStartNewQuest: () => void;
}

export default function ExploreView({
  quests,
  onSelectQuest,
  onPlayQuest,
  onStartNewQuest
}: ExploreViewProps) {
  const [search, setSearch] = useState("");
  const [filterMap, setFilterMap] = useState<string>("all");

  const filteredQuests = quests.filter((q) => {
    const matchesSearch = q.title.toLowerCase().includes(search.toLowerCase()) ||
                          q.level.toLowerCase().includes(search.toLowerCase());
    const matchesMap = filterMap === "all" || q.mapTemplateId === filterMap;
    return matchesSearch && matchesMap;
  });

  return (
    <div className="flex-grow p-6 lg:p-12 overflow-y-auto bg-surface-container-low max-h-[calc(100vh-64px)] text-on-surface">
      <div className="max-w-5xl mx-auto space-y-8 animate-fade-in">
        
        {/* Intro Hero banner */}
        <div className="relative overflow-hidden bg-gradient-to-r from-primary to-primary-container p-8 sm:p-12 rounded-3xl text-on-primary shadow-lg flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="space-y-3 max-w-lg text-center md:text-left">
            <span className="text-[10px] uppercase font-bold tracking-widest bg-white/20 px-3.5 py-1 rounded-full text-white inline-block">
              Lernabenteuer erwarten dich
            </span>
            <h1 className="font-display font-extrabold text-3xl sm:text-4xl text-white tracking-tight leading-tight">
              Erstelle & spiele interaktive Map-Quizzes
            </h1>
            <p className="text-white/80 text-xs sm:text-sm leading-relaxed">
              QuestMapper verbindet spannende Multiple-Choice-Fragen mit fesselnden virtuellen Landschaften. Kreiere eigene Welten, markiere spannende Hotspots und teile sie mit Schülern oder Freunden.
            </p>
          </div>
          <button
            onClick={onStartNewQuest}
            className="bg-white text-primary font-display font-bold px-6 py-3.5 rounded-full text-sm hover:bg-slate-50 active:scale-95 transition-all shadow-md shrink-0 cursor-pointer"
          >
            Eigene Quest entwerfen
          </button>
        </div>

        {/* Explore filters */}
        <div className="flex flex-col sm:flex-row gap-4 items-center justify-between border-b border-outline-variant/30 pb-5">
          <div className="flex items-center gap-2">
            <Compass className="w-5 h-5 text-primary" />
            <h2 className="font-display font-bold text-lg">Entdecke Abenteuer</h2>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 w-full sm:w-auto">
            {/* Search Input */}
            <div className="relative flex-grow sm:flex-grow-0">
              <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant/60" />
              <input
                type="text"
                placeholder="Quest suchen..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full sm:w-48 text-xs p-2.5 pl-8.5 bg-white border border-outline-variant rounded-xl outline-none focus:border-primary transition-all font-sans"
              />
            </div>

            {/* Template Filters */}
            <select
              value={filterMap}
              onChange={(e) => setFilterMap(e.target.value)}
              className="text-xs p-2.5 bg-white border border-outline-variant rounded-xl outline-none focus:border-primary transition-all font-sans cursor-pointer"
            >
              <option value="all">Alle Karten</option>
              <option value="forest">Nur Forest</option>
              <option value="city">Nur City</option>
              <option value="school">Nur School</option>
              <option value="island">Nur Island</option>
            </select>
          </div>
        </div>

        {/* Quests cards catalog */}
        {filteredQuests.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredQuests.map((quest) => {
              // Match background template
              const matchedTemplate = MAP_TEMPLATES.find((t) => t.id === quest.mapTemplateId) || MAP_TEMPLATES[0];

              return (
                <div
                  key={quest.id}
                  className="bg-white rounded-2xl border border-outline-variant/30 shadow-sm overflow-hidden hover:shadow-md transition-all flex flex-col group"
                >
                  {/* Thumbnail area representation */}
                  <div className="h-40 relative overflow-hidden bg-slate-100">
                    <img
                      className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-103"
                      src={matchedTemplate.image}
                      alt={quest.title}
                    />
                    <div className="absolute top-3 right-3 bg-white/95 backdrop-blur-sm shadow-sm rounded-full px-2.5 py-1 flex items-center gap-1">
                      <MapPin className="w-3 h-3 text-primary animate-bounce" />
                      <span className="text-[10px] font-extrabold text-on-surface-variant leading-none">
                        {quest.points.length} {quest.points.length === 1 ? "Pin" : "Pins"}
                      </span>
                    </div>
                  </div>

                  {/* Body information block */}
                  <div className="p-5 flex-grow flex flex-col justify-between space-y-4">
                    <div className="space-y-1">
                      <span className="text-[10px] text-primary uppercase font-extrabold tracking-wider leading-none">
                        {quest.level}
                      </span>
                      <h3 className="font-display font-bold text-md text-on-surface group-hover:text-primary transition-colors">
                        {quest.title}
                      </h3>
                      <p className="text-on-surface-variant text-xs font-sans line-clamp-2">
                        {matchedTemplate.description}
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-outline-variant/20 shrink-0">
                      <button
                        onClick={() => onSelectQuest(quest)}
                        className="flex items-center justify-center gap-1 py-2 rounded-lg border border-outline-variant text-[11px] font-semibold text-on-surface hover:bg-surface-container transition-colors cursor-pointer"
                      >
                        <Edit3 className="w-3 h-3" /> Editieren
                      </button>
                      <button
                        onClick={() => onPlayQuest(quest)}
                        className="flex items-center justify-center gap-1 py-2 rounded-lg bg-primary text-on-primary text-[11px] font-bold hover:bg-primary-container shadow-sm transition-colors cursor-pointer"
                      >
                        <Play className="w-3 h-3 text-white fill-white" /> Spielen
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="bg-white rounded-3xl p-12 text-center border border-outline-variant/40 max-w-sm mx-auto">
            <span className="material-symbols-outlined text-4xl text-primary/40 animate-pulse mb-3 block">search_off</span>
            <h3 className="font-display font-semibold text-on-surface mb-1">Keine Suchtreffer gefunden</h3>
            <p className="text-xs text-on-surface-variant max-w-xs mx-auto">
              Versuche nach einem alternativen Begriff zu suchen oder wähle andere Filter aus.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
