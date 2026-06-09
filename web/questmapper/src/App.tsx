/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useEffect } from "react";
import Header from "./components/Header";
import MapWorkspace from "./components/MapWorkspace";
import QuizEditorPanel from "./components/QuizEditorPanel";
import PlayModeGame from "./components/PlayModeGame";
import ExploreView from "./components/ExploreView";
import CommunityView from "./components/CommunityView";
import { DEFAULT_QUESTS, MAP_TEMPLATES } from "./data";
import { Quest, QuestPoint, MapTemplate } from "./types";
import { Sparkles, Trophy, Check, ArrowRight, X } from "lucide-react";

export default function App() {
  // Navigation: explore (catalog), editor (designer), community (hub)
  const [activeTab, setActiveTab] = useState<"explore" | "editor" | "community">("editor");

  // Load Quests from localStorage if available, otherwise fallback to defaults
  const [quests, setQuests] = useState<Quest[]>(() => {
    try {
      const saved = localStorage.getItem("questmapper_custom_quests");
      return saved ? JSON.parse(saved) : DEFAULT_QUESTS;
    } catch {
      return DEFAULT_QUESTS;
    }
  });

  // Track active quest ID
  const [activeQuestId, setActiveQuestId] = useState<string>(() => {
    try {
      const saved = localStorage.getItem("questmapper_active_quest_id");
      return saved || DEFAULT_QUESTS[0].id;
    } catch {
      return DEFAULT_QUESTS[0].id;
    }
  });

  // Track custom map templates uploaded by user
  const [customMaps, setCustomMaps] = useState<MapTemplate[]>(() => {
    try {
      const saved = localStorage.getItem("questmapper_custom_maps");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });

  // Selected Pin coordinates ID
  const [selectedPointId, setSelectedPointId] = useState<string | null>(null);

  // Live Game states
  const [isPlayMode, setIsPlayMode] = useState<boolean>(false);
  const [gameAnswers, setGameAnswers] = useState<Record<string, number>>({});

  // Toast notifications
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Synchronize quests state with localStorage
  useEffect(() => {
    try {
      localStorage.setItem("questmapper_custom_quests", JSON.stringify(quests));
    } catch (e) {
      console.error("Failed to save quests:", e);
    }
  }, [quests]);

  useEffect(() => {
    try {
      localStorage.setItem("questmapper_active_quest_id", activeQuestId);
    } catch (e) {
      console.error("Failed to save active quest ID:", e);
    }
    // Deselect any pin when changing active quest
    setSelectedPointId(null);
  }, [activeQuestId]);

  useEffect(() => {
    try {
      localStorage.setItem("questmapper_custom_maps", JSON.stringify(customMaps));
    } catch (e) {
      console.error("Failed to save custom maps:", e);
    }
  }, [customMaps]);

  // Find currently active quest
  const activeQuest = quests.find((q) => q.id === activeQuestId) || quests[0] || DEFAULT_QUESTS[0];

  // Helper trigger to display toast messages
  const triggerToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => {
      setToastMessage(null);
    }, 3500);
  };

  // 1. Update general Quest properties
  const handleUpdateQuestInfo = (title: string, level: string) => {
    setQuests((prev) =>
      prev.map((q) => (q.id === activeQuest.id ? { ...q, title, level } : q))
    );
  };

  // 2. Map Template Selection
  const handleSelectMapTemplate = (mapTemplateId: string) => {
    setQuests((prev) =>
      prev.map((q) => (q.id === activeQuest.id ? { ...q, mapTemplateId } : q))
    );
    // Find name
    const foundTemplate = [...MAP_TEMPLATES, ...customMaps].find((m) => m.id === mapTemplateId);
    if (foundTemplate) {
      triggerToast(`Karte zu ${foundTemplate.name} geändert!`);
    }
  };

  // 3. User adds a Custom Map template
  const handleAddCustomMap = (name: string, url: string) => {
    const newMap: MapTemplate = {
      id: `custom-${Date.now()}`,
      name,
      image: url,
      thumb: url,
      description: `Eigene Kreation: ${name}`
    };
    setCustomMaps((prev) => [...prev, newMap]);
    // Set newly created map immediately as active layout
    handleSelectMapTemplate(newMap.id);
    triggerToast(`Eigene Karte "${name}" wurde hinzugefügt und geladen!`);
  };

  // 4. Coordinates Placement (Add Point)
  const handleAddPointCoordinate = (x: number, y: number) => {
    const pointId = `pt-${Date.now()}`;
    const nextPointsCount = activeQuest.points.length + 1;
    const newPoint: QuestPoint = {
      id: pointId,
      x,
      y,
      question: `Neue Frage für Quest-Punkt ${nextPointsCount}`,
      answers: [
        "Antwortoption A",
        "Antwortoption B",
        "Antwortoption C",
        "Antwortoption D"
      ],
      correctAnswerIndex: 0
    };

    setQuests((prev) =>
      prev.map((q) => {
        if (q.id === activeQuest.id) {
          return {
            ...q,
            points: [...q.points, newPoint]
          };
        }
        return q;
      })
    );

    // Auto select newly created point for easy editing
    setSelectedPointId(pointId);
    triggerToast(`Spielfeld #${nextPointsCount} erfolgreich platziert!`);
  };

  // 5. Reposition selected pin on the map
  const handleMovePointCoordinate = (id: string, x: number, y: number) => {
    setQuests((prev) =>
      prev.map((q) => {
        if (q.id === activeQuest.id) {
          return {
            ...q,
            points: q.points.map((pt) => (pt.id === id ? { ...pt, x, y } : pt))
          };
        }
        return q;
      })
    );
  };

  // 6. Update single Point config details
  const handleSavePointQuestion = (pointId: string, updated: Partial<QuestPoint>) => {
    setQuests((prev) =>
      prev.map((q) => {
        if (q.id === activeQuest.id) {
          return {
            ...q,
            points: q.points.map((pt) => (pt.id === pointId ? { ...pt, ...updated } : pt))
          };
        }
        return q;
      })
    );
    triggerToast("Rätselfrage-Konfiguration wurde gespeichert!");
  };

  // 7. Delete coordinate point from Quest list
  const handleDeletePoint = (pointId: string) => {
    setQuests((prev) =>
      prev.map((q) => {
        if (q.id === activeQuest.id) {
          return {
            ...q,
            points: q.points.filter((pt) => pt.id !== pointId)
          };
        }
        return q;
      })
    );
    setSelectedPointId(null);
    triggerToast("Spielfeld gelöscht.");
  };

  // 8. Publish simulation trigger
  const handlePublishQuiz = () => {
    if (activeQuest.points.length === 0) {
      triggerToast("Bitte füge zuerst mindestens einen Rätselpunkt hinzu!");
      return;
    }
    triggerToast("🎉 Erfolg! Dein Quiz wurde auf QuestMapper veröffentlicht.");
  };

  // 9. Play Mode operations
  const handleTogglePlayMode = () => {
    if (!isPlayMode) {
      if (activeQuest.points.length === 0) {
        triggerToast("Füge erst Rätselfelder hinzu, bevor du den Playmodus startest!");
        return;
      }
      // Start session
      setGameAnswers({});
      setSelectedPointId(null);
      setIsPlayMode(true);
      triggerToast("🎮 Abenteuer-Modus gestartet! Löse alle Rätsel.");
    } else {
      setIsPlayMode(false);
      triggerToast("Editor aufgerufen.");
    }
  };

  const handlePlayAnswer = (pointId: string, answerIndex: number) => {
    setGameAnswers((prev) => ({
      ...prev,
      [pointId]: answerIndex
    }));
  };

  const handleResetGame = () => {
    setGameAnswers({});
    setSelectedPointId(null);
    triggerToast("Quest zurückgesetzt.");
  };

  // 10. Start a draft new quest
  const handleStartNewQuest = () => {
    const newId = `quest-${Date.now()}`;
    const newQuest: Quest = {
      id: newId,
      title: "Neues Abenteuer",
      level: "Level 1: Startzone",
      mapTemplateId: "forest",
      points: []
    };
    setQuests((prev) => [...prev, newQuest]);
    setActiveQuestId(newId);
    setActiveTab("editor");
    triggerToast("Neues Abenteuer-Template entworfen!");
  };

  // Setup current template helper
  const selectedTemplate =
    [...MAP_TEMPLATES, ...customMaps].find((t) => t.id === activeQuest.mapTemplateId) ||
    MAP_TEMPLATES[0];

  return (
    <div className="flex flex-col min-h-screen bg-background font-sans text-on-surface antialiased overflow-hidden">
      {/* Dynamic Toast notifications bar */}
      {toastMessage && (
        <div className="fixed top-20 left-1/2 -translate-x-1/2 z-100 bg-on-surface text-white text-xs sm:text-sm font-semibold px-4.5 py-3 rounded-full shadow-2xl border border-white/10 flex items-center gap-2 animate-bounce-short">
          <Sparkles className="w-4 h-4 text-secondary-container" />
          <span>{toastMessage}</span>
          <button onClick={() => setToastMessage(null)} className="ml-1 cursor-pointer">
            <X className="w-3 h-3.5 hover:text-red-400" />
          </button>
        </div>
      )}

      {/* Main Header Menu Navbar */}
      <Header
        activeTab={activeTab}
        setActiveTab={(tab) => {
          setActiveTab(tab);
          // Turn off play mode when leaving the primary workspace
          if (tab !== "editor") setIsPlayMode(false);
        }}
        onPublish={handlePublishQuiz}
        questCount={quests.length}
      />

      {/* Sub-panels display routing */}
      {activeTab === "explore" && (
        <ExploreView
          quests={quests}
          onSelectQuest={(quest) => {
            setActiveQuestId(quest.id);
            setActiveTab("editor");
          }}
          onPlayQuest={(quest) => {
            setActiveQuestId(quest.id);
            setGameAnswers({});
            setSelectedPointId(null);
            setIsPlayMode(true);
            setActiveTab("editor");
          }}
          onStartNewQuest={handleStartNewQuest}
        />
      )}

      {activeTab === "community" && (
        <CommunityView
          quests={quests}
          onPlayQuest={(quest) => {
            // Setup this temporary mock quest
            setQuests((prev) => {
              if (prev.find((p) => p.id === quest.id)) return prev;
              return [...prev, quest];
            });
            setActiveQuestId(quest.id);
            setGameAnswers({});
            setSelectedPointId(null);
            setIsPlayMode(true);
            setActiveTab("editor");
          }}
        />
      )}

      {activeTab === "editor" && (
        <main className="flex flex-col lg:flex-row h-[calc(100vh-64px)] overflow-hidden shrink-0 relative">
          
          {/* Interactive Workspace Area */}
          <MapWorkspace
            mapTemplate={selectedTemplate}
            points={activeQuest.points}
            selectedPointId={selectedPointId}
            onSelectPoint={(id) => setSelectedPointId(id)}
            onAddPoint={handleAddPointCoordinate}
            onMovePoint={handleMovePointCoordinate}
            isPlayMode={isPlayMode}
            onPlayAnswer={handlePlayAnswer}
            gameAnswers={gameAnswers}
          />

          {/* Configuration Right Sidebar Editor bar */}
          <QuizEditorPanel
            quest={activeQuest}
            onUpdateQuestInfo={handleUpdateQuestInfo}
            selectedMapId={activeQuest.mapTemplateId}
            onSelectMap={handleSelectMapTemplate}
            customMaps={customMaps}
            onAddCustomMap={handleAddCustomMap}
            selectedPoint={
              activeQuest.points.find((pt) => pt.id === selectedPointId) || null
            }
            onSavePointQuestion={handleSavePointQuestion}
            onDeletePoint={handleDeletePoint}
            isPlayMode={isPlayMode}
            onTogglePlayMode={handleTogglePlayMode}
          />

          {/* Gamified Play layer popup on top of the workspace */}
          {isPlayMode && (
            <PlayModeGame
              quest={activeQuest}
              selectedPoint={
                activeQuest.points.find((pt) => pt.id === selectedPointId) || null
              }
              onSelectPoint={(id) => setSelectedPointId(id)}
              gameAnswers={gameAnswers}
              onPlayAnswer={handlePlayAnswer}
              onResetGame={handleResetGame}
              onExitPlayMode={() => setIsPlayMode(false)}
            />
          )}

        </main>
      )}
    </div>
  );
}
