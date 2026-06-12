/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from "react";
import { Trophy, ArrowLeft, RotateCcw, CheckCircle2, Award, Calendar, Lightbulb, User } from "lucide-react";
import { Quest, QuestPoint } from "../types";

interface PlayModeGameProps {
  quest: Quest;
  selectedPoint: QuestPoint | null;
  onSelectPoint: (id: string | null) => void;
  gameAnswers: Record<string, number>;
  onPlayAnswer: (pointId: string, answerIndex: number) => void;
  onResetGame: () => void;
  onExitPlayMode: () => void;
}

export default function PlayModeGame({
  quest,
  selectedPoint,
  onSelectPoint,
  gameAnswers,
  onPlayAnswer,
  onResetGame,
  onExitPlayMode
}: PlayModeGameProps) {
  // Score calculations
  const totalPoints = quest.points.length;
  const answeredPointsList = Object.keys(gameAnswers);
  const attemptedCount = answeredPointsList.length;
  const correctCount = quest.points.reduce((acc, pt) => {
    const selected = gameAnswers[pt.id];
    return selected !== undefined && selected === pt.correctAnswerIndex ? acc + 1 : acc;
  }, 0);

  const isQuestFinished = attemptedCount === totalPoints && totalPoints > 0;
  const progressPercent = totalPoints > 0 ? Math.round((attemptedCount / totalPoints) * 100) : 0;

  // Track state of current question click
  const isSelectedAttempted = selectedPoint ? gameAnswers[selectedPoint.id] !== undefined : false;
  const selectedPlayerAnswer = selectedPoint ? gameAnswers[selectedPoint.id] : null;

  return (
    <div className="absolute inset-0 bg-black/40 backdrop-blur-[2px] z-40 flex items-center justify-center p-4">
      {/* 1. Finished Quest Overlay screen */}
      {isQuestFinished ? (
        <div className="bg-white max-w-md w-full rounded-card shadow-xl p-8 border border-outline-variant/40 text-center animate-fade-in text-on-surface">
          <div className="w-20 h-20 bg-secondary-container text-on-secondary-container mx-auto rounded-full flex items-center justify-center mb-5 animate-pulse">
            <Trophy className="w-10 h-10 text-teal-600" />
          </div>

          <span className="text-[10px] uppercase tracking-widest font-extrabold text-secondary bg-secondary-container px-3.5 py-1 rounded-full border border-secondary/20">
            QUEST ERFOLGREICH!
          </span>

          <h2 className="font-display font-extrabold text-2xl text-on-surface mt-4 mb-2">
            {quest.title} gelöst!
          </h2>
          <p className="text-on-surface-variant text-xs sm:text-sm mb-6 max-w-sm mx-auto">
            Du hast alle Rätselpunkte auf der Karte untersucht und erfolgreich beantwortet. Herzlichen Glückwunsch!
          </p>

          {/* Stats recap */}
          <div className="bg-surface-container border border-outline-variant/30 rounded-2xl p-4 mb-6 grid grid-cols-2 gap-3 divide-x divide-outline-variant/30 text-center">
            <div>
              <span className="block text-xs text-on-surface-variant font-medium">Ergebnis</span>
              <span className="font-display font-extrabold text-xl text-primary">
                {correctCount} / {totalPoints}
              </span>
            </div>
            <div>
              <span className="block text-xs text-on-surface-variant font-medium">Genauigkeit</span>
              <span className="font-display font-extrabold text-xl text-secondary">
                {Math.round((correctCount / (totalPoints || 1)) * 100)}%
              </span>
            </div>
          </div>

          <div className="flex gap-3">
            <button
              onClick={onResetGame}
              className="w-1/2 flex items-center justify-center gap-1.5 py-3 border border-outline-variant hover:bg-surface-container rounded-xl text-xs font-semibold text-on-surface transition-all cursor-pointer"
            >
              <RotateCcw className="w-4 h-4" /> Replay
            </button>
            <button
              onClick={onExitPlayMode}
              className="w-1/2 bg-primary text-on-primary font-display font-bold py-3 rounded-xl shadow-md hover:bg-primary-container active:scale-95 transition-all text-xs cursor-pointer btn-tactile"
            >
              Editor aufrufen
            </button>
          </div>
        </div>
      ) : (
        /* 2. Ongoing gameplay box */
        <div className="bg-white max-w-lg w-full rounded-card border border-outline-variant/30 shadow-2xl overflow-hidden flex flex-col relative z-20 text-on-surface animate-fade-in max-h-[90vh]">
          {/* Header progress line */}
          <div className="bg-surface p-4 border-b border-outline-variant/30 flex items-center justify-between">
            <div>
              <span className="text-[10px] text-primary uppercase font-extrabold tracking-wider filter leading-none">
                {quest.level}
              </span>
              <h2 className="font-display font-extrabold text-md text-on-surface mt-0.5">
                {quest.title}
              </h2>
            </div>
            <button
              onClick={onExitPlayMode}
              className="flex items-center gap-1 text-xs text-on-surface-variant hover:text-red-600 transition-colors bg-surface-container px-2.5 py-1.5 rounded-lg border border-outline-variant/20 cursor-pointer"
            >
              <ArrowLeft className="w-3.5 h-3.5" /> Beenden
            </button>
          </div>

          {/* Progress gauge bar */}
          <div className="px-5 pt-3">
            <div className="flex justify-between text-[11px] font-bold text-on-surface-variant/80 mb-1">
              <span>Quest-Fortschritt</span>
              <span>
                {attemptedCount} von {totalPoints} gelöst
              </span>
            </div>
            <div className="w-full bg-surface-container-high h-2.5 rounded-full overflow-hidden">
              <div
                className="bg-secondary h-full transition-all duration-300"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          {/* Active selected question sheet */}
          {selectedPoint ? (
            <div className="p-5 flex-grow overflow-y-auto space-y-4">
              <div className="bg-primary/5 border border-primary/10 rounded-xl p-3.5 text-center">
                <span className="text-[10px] font-bold text-primary uppercase tracking-widest block mb-1">Frage</span>
                <p className="text-on-surface font-display font-medium text-xs sm:text-sm">
                  {selectedPoint.question}
                </p>
              </div>

              {/* Multiple Choice options list */}
              <div className="space-y-2">
                {selectedPoint.answers.map((answer, idx) => {
                  const isThisOptionSelected = selectedPlayerAnswer === idx;
                  const isThisCorrectOption = selectedPoint.correctAnswerIndex === idx;

                  let buttonStyle = "border-outline-variant hover:bg-surface-container hover:border-primary/50 text-on-surface";
                  let endIcon = null;

                  if (isSelectedAttempted) {
                    if (isThisCorrectOption) {
                      // Correct option style
                      buttonStyle = "bg-secondary-container border-secondary text-on-secondary-container font-semibold ring-1 ring-secondary";
                      endIcon = <span className="text-xs bg-secondary text-white rounded-full w-5 h-5 flex items-center justify-center font-bold">✓</span>;
                    } else if (isThisOptionSelected && !isThisCorrectOption) {
                      // Player incorrectly picked this
                      buttonStyle = "bg-red-50 border-red-500 text-red-700 ring-1 ring-red-500";
                      endIcon = <span className="text-[10px] bg-red-600 text-white rounded-full w-5 h-5 flex items-center justify-center font-bold">X</span>;
                    } else {
                      buttonStyle = "opacity-40 border-outline-variant text-on-surface-variant";
                    }
                  }

                  return (
                    <button
                      key={idx}
                      disabled={isSelectedAttempted}
                      onClick={() => onPlayAnswer(selectedPoint.id, idx)}
                      className={`w-full text-left p-3.5 rounded-xl border-2 flex items-center justify-between transition-all text-xs sm:text-sm cursor-pointer ${buttonStyle}`}
                    >
                      <div className="flex items-center gap-3">
                        <span className="w-5 h-5 bg-surface-container font-bold text-xs uppercase flex items-center justify-center rounded-full text-on-surface-variant">
                          {String.fromCharCode(65 + idx)}
                        </span>
                        <span className="leading-tight">{answer}</span>
                      </div>
                      {endIcon}
                    </button>
                  );
                })}
              </div>

              {/* Result explanation and footer action */}
              {isSelectedAttempted && (
                <div className="bg-surface p-3.5 rounded-xl border border-outline-variant/30 text-center animate-fade-in">
                  <p className="text-xs font-semibold">
                    {selectedPlayerAnswer === selectedPoint.correctAnswerIndex ? (
                      <span className="text-secondary">Richtig beantwortet! Du hast 10 Erfahrungspunkte verdient. 🌟</span>
                    ) : (
                      <span className="text-red-600">Das war leider falsch! Such weiter nach Informationen auf der Karte. 🔍</span>
                    )}
                  </p>
                  <button
                    onClick={() => onSelectPoint(null)}
                    className="mt-3 bg-on-surface hover:bg-on-surface-variant text-white text-xs px-4 py-2 rounded-lg font-bold transition-all cursor-pointer"
                  >
                    Karte weiter untersuchen
                  </button>
                </div>
              )}
            </div>
          ) : (
            <div className="p-8 text-center flex-grow flex flex-col items-center justify-center">
              <div className="w-14 h-14 bg-surface rounded-full flex items-center justify-center text-primary border border-outline-variant/10 mb-4 animate-bounce">
                <span className="material-symbols-outlined !text-4xl text-primary">location_on</span>
              </div>
              <h3 className="font-display font-extrabold text-[15px] mb-1">Finde das nächste Rätsel!</h3>
              <p className="text-xs text-on-surface-variant max-w-sm leading-relaxed">
                Klicke auf einen der blinkenden blauen Pins auf der Karte, um eine Frage zu öffnen. Versuche, alle zu knacken!
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
