/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState, useRef, useEffect } from "react";
import { Plus, Minus, MapPin, Check, HelpCircle, Eye, RefreshCw } from "lucide-react";
import { QuestPoint, MapTemplate } from "../types";

interface MapWorkspaceProps {
  mapTemplate: MapTemplate;
  points: QuestPoint[];
  selectedPointId: string | null;
  onSelectPoint: (id: string | null) => void;
  onAddPoint: (x: number, y: number) => void;
  onMovePoint: (id: string, x: number, y: number) => void;
  isPlayMode: boolean;
  onPlayAnswer?: (pointId: string, answerIndex: number) => void;
  gameAnswers?: Record<string, number>; // Point ID -> Selected Index
}

export default function MapWorkspace({
  mapTemplate,
  points,
  selectedPointId,
  onSelectPoint,
  onAddPoint,
  onMovePoint,
  isPlayMode,
  onPlayAnswer,
  gameAnswers = {}
}: MapWorkspaceProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<HTMLImageElement>(null);

  // Zoom and pan states
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDraggingMap, setIsDraggingMap] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  // Track if we are dragging a pin currently, to avoid placing a new pin in the same click
  const [isDraggingPinId, setIsDraggingPinId] = useState<string | null>(null);

  // Reset zoom & pan when map template changes
  useEffect(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  }, [mapTemplate.id]);

  const handleZoomIn = () => setZoom(prev => Math.min(prev + 0.25, 5));
  const handleZoomOut = () => setZoom(prev => Math.max(prev - 0.25, 0.4));
  const handleRecenter = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    e.preventDefault();

    if (e.ctrlKey) {
      const direction = e.deltaY < 0 ? 1 : -1;
      setZoom(prev => Math.max(0.4, Math.min(5, prev + direction * 0.18)));
      return;
    }

    setPan(prev => ({
      x: prev.x - e.deltaX,
      y: prev.y - e.deltaY
    }));
  };

  // Click on map to add a point or deselect
  const handleMapClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (isDraggingMap || isDraggingPinId !== null) return;
    if (!mapRef.current) return;

    const rect = mapRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    // Calculate percentage coordinates
    const posXPercent = parseFloat(((clickX / rect.width) * 100).toFixed(1));
    const posYPercent = parseFloat(((clickY / rect.height) * 100).toFixed(1));

    // Bounds limit checking
    if (posXPercent >= 0 && posXPercent <= 100 && posYPercent >= 0 && posYPercent <= 100) {
      if (isPlayMode) {
        // In Play Mode, clicking empty map cancels active popover question
        onSelectPoint(null);
      } else {
        // In Editor Mode, place a new marker pin
        onAddPoint(posXPercent, posYPercent);
      }
    }
  };

  // Dragging a Pin
  const handlePinMouseDown = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (isPlayMode) return; // Pins can't be dragged in play mode
    setIsDraggingPinId(id);
    onSelectPoint(id);
  };

  const handlePinMouseMove = (e: React.MouseEvent) => {
    if (!isDraggingPinId || !mapRef.current) return;
    const rect = mapRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    let posXPercent = parseFloat(((clickX / rect.width) * 100).toFixed(1));
    let posYPercent = parseFloat(((clickY / rect.height) * 100).toFixed(1));

    // Clamping to boundaries
    posXPercent = Math.max(0, Math.min(100, posXPercent));
    posYPercent = Math.max(0, Math.min(100, posYPercent));

    onMovePoint(isDraggingPinId, posXPercent, posYPercent);
  };

  const handlePinMouseUp = (e: React.MouseEvent) => {
    if (isDraggingPinId) {
      e.stopPropagation();
      // Delay resetting state slightly so clicking isn't triggered on map root container
      setTimeout(() => {
        setIsDraggingPinId(null);
      }, 50);
    }
  };

  // Map panning controls via drag background
  const handleMapMouseDown = (e: React.MouseEvent) => {
    if (e.target !== mapRef.current && e.target !== containerRef.current) return;
    setIsDraggingMap(true);
    setDragStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMapMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (isDraggingPinId) {
      handlePinMouseMove(e);
      return;
    }
    if (!isDraggingMap) return;
    setPan({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y
    });
  };

  const handleMapMouseUp = () => {
    setIsDraggingMap(false);
  };

  return (
    <section
      ref={containerRef}
      onMouseDown={handleMapMouseDown}
      onMouseMove={handleMapMouseMove}
      onMouseUp={handleMapMouseUp}
      onWheel={handleWheel}
      onMouseLeave={() => {
        handleMapMouseUp();
        setIsDraggingPinId(null);
      }}
      className="flex-grow bg-surface-container-low p-6 lg:p-12 flex flex-col items-center justify-center relative overflow-hidden h-[calc(100vh-64px)] select-none"
    >
      {/* Play Mode / Editor Mode Banner overlay */}
      <div className="absolute top-4 left-6 z-20 flex gap-2.5 items-center bg-white/90 backdrop-blur-sm px-4 py-2 rounded-full border border-outline-variant/40 shadow-sm animate-fade-in">
        <div className={`w-2.5 h-2.5 rounded-full ${isPlayMode ? "bg-secondary animate-pulse" : "bg-primary"}`} />
        <span className="text-xs font-bold font-sans uppercase tracking-widest text-on-surface-variant">
          {isPlayMode ? "Game Play Aktiv" : "Quiz Editor Modus"}
        </span>
      </div>

      {/* Guide Help Info */}
      <div className="absolute top-4 right-6 z-20 hidden lg:flex items-center gap-1 bg-white/70 backdrop-blur-sm px-3.5 py-1.5 rounded-full text-xs text-on-surface-variant border border-outline-variant/20">
        <HelpCircle className="w-3.5 h-3.5 text-primary" />
        <span>
          {isPlayMode
            ? "Klicke auf Pins, um die Fragen zu beantworten!"
            : "Klicke auf die Karte, um Quest-Spielfelder zu platzieren."}
        </span>
      </div>

      {/* Primary Map Stage Container */}
      <div className="map-container w-full max-w-4xl relative z-10 flex items-center justify-center max-h-[80vh]">
        <div
          onClick={handleMapClick}
          className="map-inner bg-white p-2 sm:p-5 lg:p-8 rounded-card shadow-lifted relative overflow-hidden max-h-[75vh]"
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: "center center",
            left: `${pan.x}px`,
            top: `${pan.y}px`,
            cursor: isDraggingMap ? "grabbing" : "grab"
          }}
        >
          {/* Main Map Visual */}
          <img
            ref={mapRef}
            alt={mapTemplate.description}
            className="w-full h-auto rounded-lg select-none pointer-events-none border border-outline-variant/20 block"
            src={mapTemplate.image}
          />

          {/* Interactive Marker Pins */}
          {points.map((point, index) => {
            const isSelected = selectedPointId === point.id;

            // In Play Mode, calculate question state (not-attempted, selected correct vs incorrect)
            const playerSelection = gameAnswers[point.id];
            const isAttempted = playerSelection !== undefined;
            const isCorrect = isAttempted && playerSelection === point.correctAnswerIndex;

            // Pin Status Colors
            let pinColorClass = "bg-primary text-white";
            let iconElement = <span>{index + 1}</span>;

            if (isPlayMode) {
              if (isAttempted) {
                if (isCorrect) {
                  pinColorClass = "bg-secondary text-white shadow-lifted bg-teal-500";
                  iconElement = <Check className="w-4 h-4 text-white" />;
                } else {
                  pinColorClass = "bg-red-600 text-white shadow-lifted";
                  iconElement = <span className="font-bold text-xs">X</span>;
                }
              } else {
                pinColorClass = "bg-primary text-white pin-pulse hover:bg-primary-container";
              }
            } else {
              // Editor Mode States
              if (isSelected) {
                pinColorClass = "bg-primary-container ring-4 ring-primary text-white scale-110";
              } else {
                pinColorClass = "bg-primary text-white hover:bg-primary-container hover:scale-105";
              }
            }

            return (
              <div
                key={point.id}
                onMouseDown={(e) => handlePinMouseDown(point.id, e)}
                onMouseUp={handlePinMouseUp}
                className="absolute transform -translate-x-1/2 -translate-y-1/2 cursor-pointer z-35"
                style={{
                  left: `${point.x}%`,
                  top: `${point.y}%`
                }}
              >
                <div
                  className={`w-9 h-9 rounded-full flex items-center justify-center shadow-lg transition-all border border-white/20 select-none ${pinColorClass}`}
                >
                  <span className="material-symbols-outlined shrink-0 text-sm font-semibold flex items-center justify-center">
                    {iconElement}
                  </span>
                </div>

                {/* Micro Label Overlays on Hover */}
                <div className="absolute top-10 left-1/2 -translate-x-1/2 bg-on-surface text-white text-[10px] py-1 px-2 rounded opacity-0 hover:opacity-100 transition-opacity duration-200 whitespace-nowrap shadow-md pointer-events-none z-45">
                  {isPlayMode
                    ? isAttempted
                      ? isCorrect
                        ? "Richtig!"
                        : "Falsch beantwortet!"
                      : `Frage ${index + 1} spielen`
                    : `Quest-Punkt ${index + 1}`}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Floating Zoom & Map Utilities */}
      <div className="absolute bottom-6 left-6 flex flex-col gap-2 bg-white/90 backdrop-blur-sm p-1.5 rounded-2xl shadow-lg border border-outline-variant/30 z-30">
        <button
          onClick={handleZoomIn}
          title="Vergrößern"
          className="w-10 h-10 flex items-center justify-center text-on-surface-variant hover:text-primary hover:bg-surface-container rounded-xl transition-all cursor-pointer"
        >
          <Plus className="w-5 h-5" />
        </button>
        <button
          onClick={handleZoomOut}
          title="Verkleinern"
          className="w-10 h-10 flex items-center justify-center text-on-surface-variant hover:text-primary hover:bg-surface-container rounded-xl transition-all cursor-pointer"
        >
          <Minus className="w-5 h-5" />
        </button>
        <div className="border-t border-outline-variant/30 pt-1.5 mt-1">
          <button
            onClick={handleRecenter}
            title="Recenter & Reset"
            className="w-10 h-10 flex items-center justify-center text-on-surface-variant hover:text-primary hover:bg-surface-container rounded-xl transition-all cursor-pointer"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>
    </section>
  );
}
