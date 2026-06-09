/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from "react";
import {
  Map,
  Check,
  Upload,
  Archive,
  HelpCircle,
  Play,
  Square,
  PlusCircle,
  Plus,
  Trash2
} from "lucide-react";
import { Quest, QuestPoint, MapTemplate } from "../types";
import { MAP_TEMPLATES } from "../data";

interface QuizEditorPanelProps {
  quest: Quest;
  onUpdateQuestInfo: (title: string, level: string) => void;
  selectedMapId: string;
  onSelectMap: (mapId: string) => void;
  customMaps: MapTemplate[];
  onAddCustomMap: (name: string, url: string) => void;
  selectedPoint: QuestPoint | null;
  onSavePointQuestion: (pointId: string, updated: Partial<QuestPoint>) => void;
  onDeletePoint: (pointId: string) => void;
  isPlayMode: boolean;
  onTogglePlayMode: () => void;
}

export default function QuizEditorPanel({
  quest,
  onUpdateQuestInfo,
  selectedMapId,
  onSelectMap,
  customMaps,
  onAddCustomMap,
  selectedPoint,
  onSavePointQuestion,
  onDeletePoint,
  isPlayMode,
  onTogglePlayMode
}: QuizEditorPanelProps) {
  // Custom Map addition accordion/state
  const [showAddMapForm, setShowAddMapForm] = useState<boolean>(false);
  const [customMapName, setCustomMapName] = useState<string>("");
  const [customMapUrl, setCustomMapUrl] = useState<string>("");

  // Quiz Editor Question fields
  const [questionText, setQuestionText] = useState<string>("");
  const [answers, setAnswers] = useState<string[]>(["", "", "", ""]);
  const [correctAnswerIndex, setCorrectAnswerIndex] = useState<number>(0);

  // Sync editor fields whenever selected point changed
  React.useEffect(() => {
    if (selectedPoint) {
      setQuestionText(selectedPoint.question);
      setAnswers([
        selectedPoint.answers[0] || "",
        selectedPoint.answers[1] || "",
        selectedPoint.answers[2] || "",
        selectedPoint.answers[3] || ""
      ]);
      setCorrectAnswerIndex(selectedPoint.correctAnswerIndex ?? 0);
    } else {
      setQuestionText("");
      setAnswers(["", "", "", ""]);
      setCorrectAnswerIndex(0);
    }
  }, [selectedPoint]);

  const handleSaveQuestion = () => {
    if (!selectedPoint) return;
    onSavePointQuestion(selectedPoint.id, {
      question: questionText || "Neue Frage",
      answers: answers.map((ans, idx) => ans || `Antwort ${String.fromCharCode(65 + idx)}`),
      correctAnswerIndex: correctAnswerIndex
    });
  };

  const handleAnswerChange = (index: number, value: string) => {
    const updatedAnswers = [...answers];
    updatedAnswers[index] = value;
    setAnswers(updatedAnswers);
  };

  const handleAddCustomMapSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customMapName || !customMapUrl) return;
    onAddCustomMap(customMapName, customMapUrl);
    setCustomMapName("");
    setCustomMapUrl("");
    setShowAddMapForm(false);
  };

  // Combine standard and custom maps
  const allMaps = [...MAP_TEMPLATES, ...customMaps];

  return (
    <aside className="w-full lg:w-90 bg-surface-container-high border-l border-outline-variant/30 overflow-y-auto flex flex-col p-6 h-[calc(100vh-64px)] transition-all shrink-0">
      
      {/* 1. Project Title Block */}
      <div className="mb-6 bg-white/50 p-3.5 rounded-xl border border-outline-variant/30 flex items-center gap-4">
        <div className="w-11 h-11 bg-primary-container rounded-xl flex items-center justify-center text-on-primary-container shrink-0 shadow-sm">
          <Map className="w-5 h-5 text-primary" />
        </div>
        <div className="flex-grow">
          <input
            type="text"
            value={quest.title}
            onChange={(e) => onUpdateQuestInfo(e.target.value, quest.level)}
            disabled={isPlayMode}
            className="w-full font-display font-extrabold text-on-surface bg-transparent focus:bg-white px-1.5 py-0.5 rounded text-md border border-transparent focus:border-outline-variant outline-none transition-all disabled:pointer-events-none"
            placeholder="Quest Name"
          />
          <input
            type="text"
            value={quest.level}
            onChange={(e) => onUpdateQuestInfo(quest.title, e.target.value)}
            disabled={isPlayMode}
            className="w-full font-sans text-xs text-on-surface-variant font-medium bg-transparent focus:bg-white px-1.5 py-0.5 rounded border border-transparent focus:border-outline-variant outline-none transition-all disabled:pointer-events-none"
            placeholder="Level/Kategorie"
          />
        </div>
      </div>

      {/* 2. Select Map Template */}
      <div className="mb-6">
        <h3 className="font-display font-medium text-xs text-on-surface-variant tracking-wider uppercase mb-3">
          Karte Auswählen
        </h3>
        <div className="grid grid-cols-2 gap-2.5">
          {allMaps.map((m) => {
            const isActive = m.id === selectedMapId;
            return (
              <div
                key={m.id}
                onClick={() => !isPlayMode && onSelectMap(m.id)}
                className={`relative group cursor-pointer border rounded-xl overflow-hidden shadow-sm transition-all duration-200 ${
                  isActive
                    ? "ring-2 ring-primary border-primary bg-white scale-[1.01]"
                    : "border-transparent bg-white/60 hover:bg-white hover:shadow-md"
                } ${isPlayMode ? "opacity-60 pointer-events-none" : ""}`}
                title={m.description}
              >
                <div className="h-14 relative overflow-hidden">
                  <img
                    className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-105"
                    src={m.thumb || m.image}
                    alt={m.name}
                  />
                  {isActive && (
                    <div className="absolute top-1.5 right-1.5 bg-primary text-white rounded-full p-0.5">
                      <Check className="w-3 h-3 stroke-[3]" />
                    </div>
                  )}
                </div>
                <div className="p-1 px-2 text-[10px] uppercase tracking-wider text-center font-bold text-on-surface-variant group-hover:text-primary transition-colors">
                  {m.name}
                </div>
              </div>
            );
          })}
        </div>

        {/* Custom Map Form Trigger toggle */}
        {!isPlayMode && (
          <div className="mt-3">
            {!showAddMapForm ? (
              <button
                onClick={() => setShowAddMapForm(true)}
                className="w-full border-2 border-dashed border-outline-variant text-[13px] font-semibold text-on-surface-variant hover:border-primary hover:text-primary transition-all py-2 rounded-xl flex items-center justify-center gap-1.5 cursor-pointer bg-white/20 hover:bg-white/40"
              >
                <Plus className="w-4 h-4" /> Custom Map Hinzufügen
              </button>
            ) : (
              <form
                onSubmit={handleAddCustomMapSubmit}
                className="bg-white/80 p-3.5 rounded-xl border border-outline-variant/40 mt-1 space-y-2 animate-fade-in"
              >
                <div>
                  <label className="block text-[10px] uppercase font-bold text-on-surface-variant">
                    Name der Karte
                  </label>
                  <input
                    type="text"
                    required
                    value={customMapName}
                    onChange={(e) => setCustomMapName(e.target.value)}
                    placeholder="z.B. Hexenwald"
                    className="w-full p-2 mt-1 text-xs bg-surface border border-outline-variant rounded-lg font-sans outline-none focus:border-primary transition-all"
                  />
                </div>
                <div>
                  <label className="block text-[10px] uppercase font-bold text-on-surface-variant">
                    Bild-URL (.png, .jpg)
                  </label>
                  <input
                    type="url"
                    required
                    value={customMapUrl}
                    onChange={(e) => setCustomMapUrl(e.target.value)}
                    placeholder="https://... /map.jpg"
                    className="w-full p-2 mt-1 text-xs bg-surface border border-outline-variant rounded-lg font-sans outline-none focus:border-primary transition-all"
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => setShowAddMapForm(false)}
                    className="w-1/2 text-center text-xs py-1.5 rounded-lg hover:bg-surface-variant text-on-surface-variant transition-colors cursor-pointer"
                  >
                    Abbrechen
                  </button>
                  <button
                    type="submit"
                    className="w-1/2 text-center text-xs py-1.5 rounded-lg bg-primary text-on-primary font-bold hover:opacity-95 transition-colors cursor-pointer"
                  >
                    Speichern
                  </button>
                </div>
              </form>
            )}
          </div>
        )}
      </div>

      {/* 3. Quiz Editor Core Section */}
      <div className="flex-grow flex flex-col min-h-0">
        <div className="flex items-center justify-between mb-3 shrink-0">
          <h3 className="font-display font-medium text-xs text-on-surface-variant tracking-wider uppercase">
            {isPlayMode ? "Quiz Vorschau" : "Quiz Editor"}
          </h3>
          <span className="text-[11px] bg-secondary-container text-on-secondary-container px-2.5 py-0.5 rounded-full font-bold shadow-sm inline-block">
            {quest.points.length} {quest.points.length === 1 ? "Frage" : "Fragen"}
          </span>
        </div>

        {selectedPoint ? (
          <div className="space-y-4 flex-grow overflow-y-auto pr-1">
            {/* Form Fields enabled in Editor Mode, display-only/disabled in Play Mode */}
            <div className="space-y-4">
              <div>
                <label className="block text-xs font-semibold mb-1.5 text-on-surface">
                  Fragentext eingeben
                </label>
                <textarea
                  disabled={isPlayMode}
                  value={questionText}
                  onChange={(e) => setQuestionText(e.target.value)}
                  className="w-full p-3 bg-white rounded-xl border border-outline-variant focus:border-primary/80 focus:ring-1 focus:ring-primary outline-none transition-all resize-none text-xs sm:text-sm font-sans placeholder-on-surface-variant/40"
                  placeholder="Welches Geheimnis birgt diese Waldlichtung?"
                  rows={3}
                />
              </div>

              <div className="space-y-2.5">
                <label className="block text-xs font-semibold text-on-surface">
                  Antwortoptionen (korrekte Antwort anhaken)
                </label>

                {answers.map((answer, index) => {
                  const isCorrect = correctAnswerIndex === index;
                  return (
                    <div key={index} className="flex items-center gap-2 group">
                      <input
                        type="text"
                        disabled={isPlayMode}
                        value={answer}
                        onChange={(e) => handleAnswerChange(index, e.target.value)}
                        placeholder={`Antwortoption ${String.fromCharCode(65 + index)}`}
                        className={`flex-grow p-2.5 bg-white text-xs rounded-xl border outline-none transition-all ${
                          isCorrect
                            ? "border-secondary-container ring-1 ring-secondary font-medium"
                            : "border-outline-variant focus:border-primary"
                        }`}
                      />

                      {/* Correct answer tag check button */}
                      <button
                        type="button"
                        disabled={isPlayMode}
                        onClick={() => setCorrectAnswerIndex(index)}
                        className={`w-7 h-7 rounded-full border flex items-center justify-center shrink-0 cursor-pointer transition-all ${
                          isCorrect
                            ? "bg-secondary-container border-secondary text-on-secondary-container scale-100 shadow-sm"
                            : "border-outline-variant bg-white hover:bg-surface-variant hover:border-primary"
                        }`}
                        title="Als korrekte Antwort markieren"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Editor Action buttons */}
            {!isPlayMode && (
              <div className="pt-2 space-y-2">
                <button
                  onClick={handleSaveQuestion}
                  className="w-full bg-primary text-on-primary font-display font-bold py-3 text-xs sm:text-sm rounded-xl shadow-md hover:bg-primary-container active:scale-95 transition-all btn-tactile cursor-pointer"
                >
                  Frage Speichern
                </button>
                <button
                  type="button"
                  onClick={() => onDeletePoint(selectedPoint.id)}
                  className="w-full bg-red-50 hover:bg-red-100 text-red-600 font-display font-medium py-2 rounded-lg text-xs transition-colors flex items-center justify-center gap-1 cursor-pointer"
                >
                  <Trash2 className="w-3.5 h-3.5" /> Quest-Punkt Löschen
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="flex-grow flex flex-col items-center justify-center text-center p-4 py-8 bg-white/40 border border-dashed border-outline-variant/40 rounded-2xl select-none">
            <Map className="w-9 h-9 text-primary/40 mb-3" />
            <p className="text-xs font-semibold text-on-surface-variant max-w-[200px]">
              {isPlayMode
                ? "Klicke auf einen Pin auf der Karte, um die Quizfrage anzuzeigen!"
                : "Klicke auf die Karte, um einen Pin zu erstellen oder wähle einen aus!"}
            </p>
          </div>
        )}
      </div>

      {/* 4. Footer Utilities & Global Play Toggler */}
      <div className="mt-4 pt-4 border-t border-outline-variant/30 flex items-center justify-around shrink-0 bg-surface-container-high">
        <button
          title="Archive Map Quest"
          className="flex flex-col items-center gap-0.5 text-on-surface-variant hover:text-primary transition-all cursor-pointer"
        >
          <Archive className="w-4 h-4" />
          <span className="text-[9px] font-bold uppercase tracking-wider font-sans">Sichern</span>
        </button>

        <button
          onClick={onTogglePlayMode}
          className={`p-3.5 rounded-full scale-100 hover:scale-105 active:scale-90 transition-transform cursor-pointer shadow-md flex items-center justify-center ${
            isPlayMode
              ? "bg-red-600 text-white hover:bg-red-700"
              : "bg-primary text-on-primary hover:bg-primary-container"
          }`}
          title={isPlayMode ? "Spiel Beenden" : "Spielmodus Starten"}
        >
          {isPlayMode ? <Square className="w-4 h-4 fill-white text-white" /> : <Play className="w-4 h-4 fill-white text-white" />}
        </button>

        <button
          title="Direct Support"
          className="flex flex-col items-center gap-0.5 text-on-surface-variant hover:text-primary transition-all cursor-pointer"
        >
          <HelpCircle className="w-4 h-4" />
          <span className="text-[9px] font-bold uppercase tracking-wider font-sans">Support</span>
        </button>
      </div>
    </aside>
  );
}
