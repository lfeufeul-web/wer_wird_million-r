/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from "react";
import { Users, Heart, Share2, Award, Play, MessageSquare, Plus, Sparkles } from "lucide-react";
import { Quest } from "../types";
import { MAP_TEMPLATES } from "../data";

interface CommunityQuestItem {
  id: string;
  title: string;
  level: string;
  author: string;
  likes: number;
  comments: number;
  pointsCount: number;
  mapTemplateId: string;
  isLikedByPlayer?: boolean;
}

interface CommunityViewProps {
  onPlayQuest: (quest: Quest) => void;
  quests: Quest[];
}

export default function CommunityView({ onPlayQuest, quests }: CommunityViewProps) {
  // Pre-seed some fun community assets
  const [items, setItems] = useState<CommunityQuestItem[]>([
    {
      id: "c-1",
      title: "Geheimkammer des Sphinx",
      level: "Level 4: Die Pyramide",
      author: "Prof. Dr. Schmidt",
      likes: 142,
      comments: 18,
      pointsCount: 6,
      mapTemplateId: "city"
    },
    {
      id: "c-2",
      title: "Verlorene Relikte von Atlantis",
      level: "Level 2: Korallenhafen",
      author: "Abenteurer_Mia",
      likes: 89,
      comments: 7,
      pointsCount: 3,
      mapTemplateId: "island",
      isLikedByPlayer: true
    },
    {
      id: "c-3",
      title: "Notfallstrom-Rätsel im Schulflur",
      level: "Level 1: Physik-AG",
      author: "Lehrer_Max",
      likes: 216,
      comments: 34,
      pointsCount: 5,
      mapTemplateId: "school"
    }
  ]);

  const handleLike = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setItems((prev) =>
      prev.map((item) => {
        if (item.id === id) {
          const isLiked = !item.isLikedByPlayer;
          return {
            ...item,
            isLikedByPlayer: isLiked,
            likes: isLiked ? item.likes + 1 : item.likes - 1
          };
        }
        return item;
      })
    );
  };

  const handlePlayCommunityItem = (item: CommunityQuestItem) => {
    // Attempt to reconstruction a quick simulation Quest to feed the player
    const matchedQuest = quests.find(q => q.mapTemplateId === item.mapTemplateId) || quests[0];
    const temporaryQuest: Quest = {
      ...matchedQuest,
      title: item.title,
      level: item.level
    };
    onPlayQuest(temporaryQuest);
  };

  return (
    <div className="flex-grow p-6 lg:p-12 overflow-y-auto bg-surface-container-low max-h-[calc(100vh-64px)] text-on-surface">
      <div className="max-w-5xl mx-auto space-y-8 animate-fade-in">
        
        {/* Community introduction cards */}
        <div className="flex flex-col md:flex-row items-center justify-between gap-6 border-b border-outline-variant/30 pb-6">
          <div className="flex items-start gap-3">
            <div className="p-3 bg-primary-container text-on-primary-container rounded-2xl shadow-sm">
              <Users className="w-6 h-6 text-primary" />
            </div>
            <div>
              <h1 className="font-display font-extrabold text-2xl tracking-tight text-on-surface">
                QuestMapper Community
              </h1>
              <p className="text-on-surface-variant text-xs sm:text-sm mt-1 max-w-xl">
                Tauche ein in Hunderte von interaktiven Quizzes, die von Lehrern, Schülern und Abenteurern weltweit geteilt wurden. Vote für deine Favoriten!
              </p>
            </div>
          </div>
          <div className="bg-white px-4 py-2.5 rounded-full border border-outline-variant/40 flex items-center gap-2 shadow-sm select-none shrink-0 self-start md:self-auto">
            <Sparkles className="w-4 h-4 text-secondary fill-secondary animate-pulse" />
            <span className="text-xs font-bold text-on-surface-variant">
              872 freigegebene Quizzes live
            </span>
          </div>
        </div>

        {/* Catalog grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {items.map((item) => {
            const template = MAP_TEMPLATES.find((t) => t.id === item.mapTemplateId) || MAP_TEMPLATES[0];

            return (
              <div
                key={item.id}
                onClick={() => handlePlayCommunityItem(item)}
                className="bg-white rounded-2xl border border-outline-variant/30 shadow-none hover:shadow-lg hover:border-primary-container/40 transition-all overflow-hidden flex flex-col justify-between cursor-pointer group p-5 space-y-4"
              >
                {/* Header card representation space info */}
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-[9px] font-extrabold bg-primary/10 text-primary uppercase tracking-widest px-2.5 py-0.5 rounded-full inline-block mb-1.5">
                      {item.level}
                    </span>
                    <h3 className="font-display font-bold text-sm sm:text-[15px] leading-tight text-on-surface group-hover:text-primary transition-colors">
                      {item.title}
                    </h3>
                  </div>
                  <div className="w-10 h-10 rounded-xl overflow-hidden shadow-sm shrink-0">
                    <img
                      className="w-full h-full object-cover grayscale-[30%] group-hover:grayscale-0 transition-all"
                      src={template.thumb || template.image}
                      alt={item.title}
                    />
                  </div>
                </div>

                {/* Author attribution with custom user icons */}
                <div className="flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-surface-container-high border border-outline-variant/20 flex items-center justify-center text-[10px] text-on-surface-variant font-bold select-none">
                    {item.author[0].toUpperCase()}
                  </div>
                  <span className="text-xs text-on-surface-variant">
                    von <span className="font-semibold text-on-surface">{item.author}</span>
                  </span>
                </div>

                {/* Actions and analytics indicators footer bar */}
                <div className="border-t border-outline-variant/20 pt-3 flex items-center justify-between text-on-surface-variant text-xs">
                  <div className="flex gap-4">
                    <button
                      onClick={(e) => handleLike(item.id, e)}
                      className={`flex items-center gap-1 hover:text-red-500 transition-colors cursor-pointer select-none ${
                        item.isLikedByPlayer ? "text-red-500 font-bold" : ""
                      }`}
                    >
                      <Heart className={`w-4 h-4 ${item.isLikedByPlayer ? "fill-current" : ""}`} />
                      <span>{item.likes}</span>
                    </button>
                    <span className="flex items-center gap-1 select-none">
                      <MessageSquare className="w-4 h-4" />
                      <span>{item.comments}</span>
                    </span>
                  </div>

                  <span className="bg-secondary/10 text-secondary text-[10px] font-bold px-2 py-0.5 rounded flex items-center gap-1 select-none">
                    <Award className="w-3.5 h-3.5" /> {item.pointsCount} Levelpunkte
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Global info card */}
        <div className="bg-white/50 border border-outline-variant/30 rounded-3xl p-6 flex flex-col md:flex-row items-center justify-between gap-4 text-center md:text-left">
          <div className="space-y-1">
            <h3 className="font-display font-bold text-sm sm:text-md text-on-surface">Gemeinschaftliches Lehren</h3>
            <p className="text-xs text-on-surface-variant max-w-xl">
              Veröffentliche deine im Editor gestalteten Quest-Pfade, damit andere Benutzer sie spielen und lernen können! Deine Beiträge helfen Abenteuerlustigen weltweit.
            </p>
          </div>
          <button className="bg-on-surface hover:bg-on-surface-variant text-white text-xs font-bold px-5 py-3 rounded-xl transition-all cursor-pointer">
            Eigene Schöpfungen einreichen
          </button>
        </div>

      </div>
    </div>
  );
}
