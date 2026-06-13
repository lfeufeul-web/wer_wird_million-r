import { useEffect, useMemo, useRef, useState, type WheelEvent } from 'react';
import {
  ArrowLeft,
  Check,
  ChevronRight,
  CopyPlus,
  Edit3,
  Globe2,
  Map,
  Plus,
  Save,
  Sparkles,
  Trash2,
} from 'lucide-react';
import GameButton from '@/components/GameButton';
import Modal from '@/components/Modal';
import SectionShell from '@/components/SectionShell';
import { sampleQuestWorld } from '@/data/sampleQuestions';
import type {
  QuestIsland,
  QuestPathWorld,
  QuestPoint,
  SavedEntry,
  QuestionStatus,
} from '@/types';
import { clamp, createId, formatDate, loadJson, saveJson } from '@/utils/storage';

type QuestPathPageProps = {
  savedWorlds: SavedEntry<QuestPathWorld>[];
  onSaveWorld: (world: QuestPathWorld) => void;
  onDeleteWorld: (id: string) => void;
  onBack: () => void;
};

type ViewMode = 'world' | 'editor' | 'library';

type DragState =
  | { kind: 'world-pan'; startX: number; startY: number; originX: number; originY: number }
  | { kind: 'island'; islandId: string; startX: number; startY: number; originX: number; originY: number }
  | { kind: 'point'; islandId: string; pointId: string; startX: number; startY: number; originX: number; originY: number }
  | {
      kind: 'point-list';
      islandId: string;
      pointId: string;
      pointerId: number;
      startX: number;
      startY: number;
      currentX: number;
      currentY: number;
      grabOffsetX: number;
      grabOffsetY: number;
      sourceIndex: number;
      insertionIndex: number;
      itemWidth: number;
      itemHeight: number;
      dragged: boolean;
    }
  | null;

function cloneWorld(world: QuestPathWorld) {
  return JSON.parse(JSON.stringify(world)) as QuestPathWorld;
}

function islandEmoji(style: QuestIsland['style']) {
  const map: Record<QuestIsland['style'], string> = {
    waldinsel: '🌿',
    feuerinsel: '🔥',
    wasserinsel: '🌊',
    musikinsel: '🎵',
    magieinsel: '✨',
    eisinsel: '❄️',
    wuesteinsel: '🏜️',
    technikinsel: '⚙️',
    stadtinsel: '🏙️',
    sterneninsel: '⭐',
  };
  return map[style];
}

function islandGradient(style: QuestIsland['style']) {
  const map: Record<QuestIsland['style'], string> = {
    waldinsel: 'linear-gradient(135deg, rgba(34,197,94,.38), rgba(16,185,129,.12))',
    feuerinsel: 'linear-gradient(135deg, rgba(251,146,60,.45), rgba(239,68,68,.16))',
    wasserinsel: 'linear-gradient(135deg, rgba(14,165,233,.42), rgba(56,189,248,.18))',
    musikinsel: 'linear-gradient(135deg, rgba(236,72,153,.36), rgba(168,85,247,.18))',
    magieinsel: 'linear-gradient(135deg, rgba(168,85,247,.44), rgba(34,211,238,.18))',
    eisinsel: 'linear-gradient(135deg, rgba(186,230,253,.34), rgba(96,165,250,.14))',
    wuesteinsel: 'linear-gradient(135deg, rgba(250,204,21,.34), rgba(245,158,11,.12))',
    technikinsel: 'linear-gradient(135deg, rgba(148,163,184,.38), rgba(56,189,248,.16))',
    stadtinsel: 'linear-gradient(135deg, rgba(99,102,241,.34), rgba(14,165,233,.16))',
    sterneninsel: 'linear-gradient(135deg, rgba(255,255,255,.28), rgba(129,140,248,.14))',
  };
  return map[style];
}

function mapBackground(mapStyle: QuestIsland['mapStyle']) {
  const map: Record<QuestIsland['mapStyle'], string> = {
    waldkarte: 'radial-gradient(circle at top, rgba(34,197,94,.2), transparent 30%), linear-gradient(180deg, #07130d, #0a1626)',
    vulkan: 'radial-gradient(circle at top, rgba(251,146,60,.18), transparent 34%), linear-gradient(180deg, #180608, #2b0a10)',
    ozean: 'radial-gradient(circle at top, rgba(14,165,233,.18), transparent 30%), linear-gradient(180deg, #03111f, #041d33)',
    magie: 'radial-gradient(circle at top, rgba(168,85,247,.2), transparent 32%), linear-gradient(180deg, #100621, #180b30)',
    stadt: 'radial-gradient(circle at top, rgba(99,102,241,.18), transparent 30%), linear-gradient(180deg, #060b1e, #0b1630)',
    eis: 'radial-gradient(circle at top, rgba(186,230,253,.2), transparent 30%), linear-gradient(180deg, #07141d, #091b2e)',
    wueste: 'radial-gradient(circle at top, rgba(250,204,21,.16), transparent 30%), linear-gradient(180deg, #18100b, #302110)',
    sternenhimmel: 'radial-gradient(circle at top, rgba(255,255,255,.15), transparent 28%), linear-gradient(180deg, #04040d, #0b1025)',
    labor: 'radial-gradient(circle at top, rgba(148,163,184,.16), transparent 30%), linear-gradient(180deg, #050a12, #0d1726)',
    musik: 'radial-gradient(circle at top, rgba(236,72,153,.16), transparent 30%), linear-gradient(180deg, #170717, #0f1027)',
  };
  return map[mapStyle];
}

function calcProgress(points: QuestPoint[]) {
  const total = points.length || 1;
  const complete = points.filter((point) => point.status !== 'open').length;
  return Math.round((complete / total) * 100);
}

function makeDefaultPoint(title: string, x: number, y: number): QuestPoint {
  return {
    id: createId('point'),
    title,
    prompt: 'Neue Frage',
    answers: ['Antwort A', 'Antwort B', 'Antwort C', 'Antwort D'],
    correctIndices: [0],
    multipleCorrect: false,
    explanation: '',
    points: 20,
    x,
    y,
    status: 'open',
  };
}

function reorderPoints(points: QuestPoint[], pointId: string, insertionIndex: number) {
  const currentIndex = points.findIndex((point) => point.id === pointId);
  if (currentIndex < 0) return points;
  const next = [...points];
  const [moved] = next.splice(currentIndex, 1);
  const targetIndex = clamp(insertionIndex > currentIndex ? insertionIndex - 1 : insertionIndex, 0, next.length);
  next.splice(targetIndex, 0, moved);
  return next;
}

export default function QuestPathPage({ savedWorlds, onSaveWorld, onDeleteWorld, onBack }: QuestPathPageProps) {
  const [view, setView] = useState<ViewMode>('world');
  const [world, setWorld] = useState<QuestPathWorld>(() => cloneWorld(sampleQuestWorld));
  const [selectedIslandId, setSelectedIslandId] = useState<string | null>(world.islands[0]?.id ?? null);
  const [selectedPointId, setSelectedPointId] = useState<string | null>(null);
  const [worldEditMode, setWorldEditMode] = useState(true);
  const [islandEditMode, setIslandEditMode] = useState(false);
  const [worldView, setWorldView] = useState(() => loadJson('questmapper.questpath.worldview.v1', { x: 0, y: 0, scale: 1 }));
  const [islandView, setIslandView] = useState({ x: 0, y: 0, scale: 1 });
  const [activeQuestionState, setActiveQuestionState] = useState<{ islandId: string; pointId: string; selected: number[] } | null>(null);
  const [dragState, setDragState] = useState<DragState>(null);
  const dragRef = useRef<DragState>(null);
  const pointListRef = useRef<HTMLDivElement>(null);
  const suppressPointClickRef = useRef(false);

  const selectedIsland = useMemo(
    () => world.islands.find((island) => island.id === selectedIslandId) ?? null,
    [selectedIslandId, world.islands],
  );
  const activePointCount = selectedIsland?.points.length ?? 0;

  const selectIsland = (islandId: string | null) => {
    setSelectedIslandId(islandId);
    setSelectedPointId(null);
    setActiveQuestionState(null);
  };

  useEffect(() => {
    saveJson('questmapper.questpath.worldview.v1', worldView);
  }, [worldView]);

  useEffect(() => {
    dragRef.current = dragState;
  }, [dragState]);

  useEffect(() => {
    const handleMove = (event: PointerEvent) => {
      const drag = dragRef.current;
      if (!drag) return;
      if (drag.kind === 'world-pan') {
        setWorldView((prev) => ({ ...prev, x: drag.originX + (event.clientX - drag.startX), y: drag.originY + (event.clientY - drag.startY) }));
        return;
      }
      if (drag.kind === 'island') {
        setWorld((prev) => ({
          ...prev,
          islands: prev.islands.map((island) =>
            island.id === drag.islandId
              ? {
                  ...island,
                  x: drag.originX + (event.clientX - drag.startX) / worldView.scale,
                  y: drag.originY + (event.clientY - drag.startY) / worldView.scale,
                }
              : island,
          ),
        }));
        return;
      }
      if (drag.kind === 'point') {
        setWorld((prev) => ({
          ...prev,
          islands: prev.islands.map((island) =>
            island.id === drag.islandId
              ? {
                  ...island,
                  points: island.points.map((point) =>
                    point.id === drag.pointId
                      ? {
                          ...point,
                          x: drag.originX + (event.clientX - drag.startX) / islandView.scale,
                          y: drag.originY + (event.clientY - drag.startY) / islandView.scale,
                        }
                      : point,
                  ),
                }
              : island,
          ),
        }));
        return;
      }
      if (drag.kind === 'point-list') {
        const list = pointListRef.current;
        if (!list) return;
        const rect = list.getBoundingClientRect();
        const slotHeight = drag.itemHeight + 10;
        const relativeY = event.clientY - rect.top + list.scrollTop;
        const insertionIndex = clamp(Math.floor(relativeY / slotHeight), 0, activePointCount);
        const moved = Math.abs(event.clientX - drag.startX) > 4 || Math.abs(event.clientY - drag.startY) > 4;
        const nextDrag = { ...drag, currentX: event.clientX, currentY: event.clientY, insertionIndex, dragged: drag.dragged || moved };
        dragRef.current = nextDrag;
        setDragState(nextDrag);
      }
    };

    const handleUp = () => {
      const drag = dragRef.current;
      if (drag && drag.kind === 'point-list') {
        const wasDragged = drag.dragged;
        if (wasDragged) {
          setWorld((prev) => ({
            ...prev,
            islands: prev.islands.map((island) =>
              island.id === drag.islandId
                ? {
                    ...island,
                    points: reorderPoints(island.points, drag.pointId, drag.insertionIndex),
                  }
                : island,
            ),
          }));
        }
        suppressPointClickRef.current = wasDragged;
        window.setTimeout(() => {
          suppressPointClickRef.current = false;
        }, 80);
      }
      setDragState(null);
    };

    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp);
    return () => {
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
    };
  }, [activePointCount, islandView.scale, worldView.scale]);

  const openIsland = (islandId: string) => {
    selectIsland(islandId);
    setDragState(null);
    setIslandView({ x: 0, y: 0, scale: 1 });
    setView('world');
  };

  const saveCurrentWorld = () => {
    onSaveWorld({
      ...world,
      scale: worldView.scale,
      offsetX: worldView.x,
      offsetY: worldView.y,
    });
  };

  const loadSavedWorld = (entry: SavedEntry<QuestPathWorld>) => {
    const next = cloneWorld(entry.data);
    setWorld(next);
    setWorldView({ x: next.offsetX ?? 0, y: next.offsetY ?? 0, scale: next.scale ?? 1 });
    selectIsland(next.islands[0]?.id ?? null);
    setView('world');
  };

  const addIsland = () => {
    const newIsland: QuestIsland = {
      id: createId('island'),
      name: `Insel ${world.islands.length + 1}`,
      description: 'Eine neue Insel im Archipel.',
      x: 100 + world.islands.length * 120,
      y: 120 + world.islands.length * 80,
      style: 'magieinsel',
      mapStyle: 'magie',
      completed: false,
      progress: 0,
      points: [makeDefaultPoint('Frage 1', 18, 22), makeDefaultPoint('Frage 2', 52, 46), makeDefaultPoint('Frage 3', 78, 18)],
    };
    setWorld((prev) => ({ ...prev, islands: [...prev.islands, newIsland] }));
    selectIsland(newIsland.id);
  };

  const updateIsland = (islandId: string, patch: Partial<QuestIsland>) => {
    setWorld((prev) => ({
      ...prev,
      islands: prev.islands.map((island) => (island.id === islandId ? { ...island, ...patch } : island)),
    }));
  };

  const deleteIsland = (islandId: string) => {
    let nextIslands: QuestIsland[] = [];
    setWorld((prev) => {
      nextIslands = prev.islands.filter((island) => island.id !== islandId);
      return { ...prev, islands: nextIslands };
    });
    if (selectedIslandId === islandId) {
      setDragState(null);
      selectIsland(nextIslands[0]?.id ?? null);
    }
  };

  const addPoint = () => {
    if (!selectedIsland) return;
    updateIsland(selectedIsland.id, {
      points: [...selectedIsland.points, makeDefaultPoint(`Punkt ${selectedIsland.points.length + 1}`, 30 + selectedIsland.points.length * 12, 30)],
    });
  };

  const updatePoint = (islandId: string, pointId: string, patch: Partial<QuestPoint>) => {
    updateIsland(islandId, {
      points: world.islands
        .find((island) => island.id === islandId)!
        .points.map((point) => (point.id === pointId ? { ...point, ...patch } : point)),
    });
  };

  const answerPoint = (result: QuestionStatus) => {
    if (!activeQuestionState) return;
    const island = world.islands.find((item) => item.id === activeQuestionState.islandId);
    const point = island?.points.find((item) => item.id === activeQuestionState.pointId);
    if (!island || !point) return;
    const nextStatus: QuestionStatus = result === 'correct' ? 'correct' : 'wrong';
    updatePoint(island.id, point.id, { status: nextStatus });
    setActiveQuestionState(null);
    const nextIsland = world.islands.find((item) => item.id === island.id);
    if (nextIsland && calcProgress(nextIsland.points) >= 100) {
      updateIsland(nextIsland.id, { completed: true, progress: 100 });
    } else {
      updateIsland(island.id, { progress: calcProgress(island.points) });
    }
  };

  const startPlayingIsland = (islandId: string) => {
    selectIsland(islandId);
    setIslandEditMode(false);
    setView('world');
  };

  const nextIsland = () => {
    if (!selectedIsland) return;
    const index = world.islands.findIndex((item) => item.id === selectedIsland.id);
    const next = world.islands[index + 1] ?? world.islands[0];
    if (next) {
      openIsland(next.id);
    }
  };

  const activeIsland = selectedIsland;
  const activePoints = activeIsland?.points ?? [];
  const islandProgress = calcProgress(activePoints);
  const completedIslands = world.islands.filter((island) => island.progress >= 100).length;

  const onWorldWheel = (event: WheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    const delta = event.deltaY > 0 ? -0.08 : 0.08;
    setWorldView((prev) => ({ ...prev, scale: clamp(prev.scale + delta, 0.65, 1.8) }));
  };

  const onIslandWheel = (event: WheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    const delta = event.deltaY > 0 ? -0.08 : 0.08;
    setIslandView((prev) => ({ ...prev, scale: clamp(prev.scale + delta, 0.75, 2) }));
  };

  const worldCanvasStyle = {
    transform: `translate(${worldView.x}px, ${worldView.y}px) scale(${worldView.scale})`,
  } as const;

  const islandCanvasStyle = {
    transform: `translate(${islandView.x}px, ${islandView.y}px) scale(${islandView.scale})`,
  } as const;

  return (
    <SectionShell
      eyebrow="Spielmodus 3"
      title="Fragen-Pfad"
      action={
        <div className="row-actions">
          <GameButton variant="secondary" onClick={() => setView('world')}>
            Weltkarte
          </GameButton>
          <GameButton variant="secondary" onClick={() => setView('editor')}>
            Bearbeiten
          </GameButton>
          <GameButton variant="secondary" onClick={() => setView('library')}>
            Gespeichert
          </GameButton>
          <GameButton variant="ghost" onClick={onBack}>
            Zurueck
          </GameButton>
        </div>
      }
    >
      <div className="quest-layout">
        <div className="compact-grid">
          <div className="glass panel-block">
            <div className="hero-strip">
              <span className="floating-tag"><Globe2 size={16} /> {world.name}</span>
              <span className="floating-tag"><Sparkles size={16} /> {world.theme}</span>
              <span className="floating-tag">Inseln: {world.islands.length}</span>
            </div>
            <div className="row-actions">
              <GameButton icon={<Plus size={16} />} onClick={addIsland}>
                Insel hinzufuegen
              </GameButton>
              <GameButton variant="secondary" icon={<Save size={16} />} onClick={saveCurrentWorld}>
                Speichern
              </GameButton>
              <GameButton variant="ghost" onClick={() => setWorldEditMode((prev) => !prev)}>
                {worldEditMode ? 'Editmodus an' : 'Editmodus aus'}
              </GameButton>
            </div>
          </div>

          {view === 'library' ? (
            <div className="glass panel-block">
              <h3>Gespeicherte Welten</h3>
              <div className="stack-list">
                {savedWorlds.map((entry) => (
                  <article key={entry.id} className="list-card" style={{ display: 'grid' }}>
                    <strong>{entry.name}</strong>
                    <span>{formatDate(entry.updatedAt)}</span>
                    <div className="row-actions">
                      <GameButton size="sm" onClick={() => loadSavedWorld(entry)}>
                        Spielen
                      </GameButton>
                      <GameButton variant="secondary" size="sm" onClick={() => loadSavedWorld(entry)}>
                        Laden
                      </GameButton>
                      <GameButton variant="ghost" size="sm" onClick={() => onDeleteWorld(entry.id)}>
                        <Trash2 size={14} />
                      </GameButton>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          {view === 'editor' ? (
            <div className="glass panel-block">
              <h3>Welteditor</h3>
              <div className="form-grid">
                <label className="inline-field">
                  <span>Weltname</span>
                  <input value={world.name} onChange={(event) => setWorld((prev) => ({ ...prev, name: event.target.value }))} />
                </label>
                <label className="inline-field">
                  <span>Thema</span>
                  <select value={world.theme} onChange={(event) => setWorld((prev) => ({ ...prev, theme: event.target.value as QuestPathWorld['theme'] }))}>
                    <option value="fantasy">Fantasy</option>
                    <option value="wald">Wald</option>
                    <option value="feuer">Feuer</option>
                    <option value="wasser">Wasser</option>
                    <option value="magie">Magie</option>
                    <option value="stadt">Stadt</option>
                    <option value="gemischt">Gemischt</option>
                  </select>
                </label>
              </div>
              <div className="row-actions">
                <GameButton variant="secondary" onClick={addPoint}>
                  Punkt hinzufuegen
                </GameButton>
                <GameButton variant="secondary" onClick={() => setIslandEditMode((prev) => !prev)}>
                  {islandEditMode ? 'Punkte bewegen aus' : 'Punkte bewegen an'}
                </GameButton>
              </div>
              <div className="stack-list">
                {world.islands.map((island) => (
                  <article key={island.id} className="list-card" style={{ display: 'grid' }}>
                    <strong>{island.name}</strong>
                    <span>{island.description}</span>
                    <div className="row-actions">
                      <GameButton size="sm" variant="secondary" onClick={() => selectIsland(island.id)}>
                        Auswaehlen
                      </GameButton>
                      <GameButton size="sm" variant="ghost" onClick={() => deleteIsland(island.id)}>
                        <Trash2 size={14} />
                      </GameButton>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : null}
        </div>

        <div className="world-stage glass">
          <div
            className="world-stage__canvas"
            onWheel={onWorldWheel}
            onPointerDown={(event) => {
              if (event.button !== 0) return;
              if ((event.target as HTMLElement).closest('.island-card')) return;
              selectIsland(null);
              setDragState({
                kind: 'world-pan',
                startX: event.clientX,
                startY: event.clientY,
                originX: worldView.x,
                originY: worldView.y,
              });
            }}
          >
            <div className="world-stage__layer" style={worldCanvasStyle}>
              {world.islands.map((island) => (
                <button
                  key={island.id}
                  type="button"
                  className={`island-card glass ${island.completed ? 'island-card--completed' : ''}`}
                  style={{ left: island.x, top: island.y, background: islandGradient(island.style) }}
                  onClick={() => {
                    if (worldEditMode) {
                      selectIsland(island.id);
                      return;
                    }
                    openIsland(island.id);
                  }}
                  onPointerDown={(event) => {
                    if (!worldEditMode || event.button !== 0) return;
                    event.stopPropagation();
                    setDragState({
                      kind: 'island',
                      islandId: island.id,
                      startX: event.clientX,
                      startY: event.clientY,
                      originX: island.x,
                      originY: island.y,
                    });
                  }}
                >
                  <span className="island-card__badge">{islandEmoji(island.style)}</span>
                  <h3 className="island-card__title" style={{ marginTop: 12 }}>{island.name}</h3>
                  <div className="island-card__meta">
                    <span>{island.description}</span>
                    <span>{island.progress}% Fortschritt</span>
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="quest-sidebar">
          <div className="glass sidebar-block">
            <div className="row-actions" style={{ justifyContent: 'space-between' }}>
              <h3 style={{ margin: 0 }}>Inselinfo</h3>
              <span className="floating-tag">
                <Map size={14} /> {completedIslands}/{world.islands.length}
              </span>
            </div>
            {selectedIsland ? (
              <div className="compact-grid" style={{ marginTop: 12 }}>
                <strong>{selectedIsland.name}</strong>
                <span className="muted">{selectedIsland.description}</span>
                <span className="status-pill status-pill--good">{selectedIsland.progress}% erledigt</span>
                <div className="row-actions">
                  <GameButton variant="secondary" size="sm" onClick={() => selectIsland(selectedIsland.id)}>
                    Im Fokus
                  </GameButton>
                  {!worldEditMode && view !== 'editor' ? (
                    <GameButton size="sm" onClick={() => startPlayingIsland(selectedIsland.id)}>
                      Spielen
                    </GameButton>
                  ) : null}
                  <GameButton variant="ghost" size="sm" onClick={nextIsland}>
                    Naechste Insel <ChevronRight size={14} />
                  </GameButton>
                </div>
              </div>
            ) : (
              <p className="muted">Waehl eine Insel auf der Weltkarte aus.</p>
            )}
          </div>

          <div className="glass sidebar-block">
            <h3>Fragepunkte</h3>
            <div className="sidebar-list" ref={pointListRef}>
              {activePoints.map((point) => (
                <button
                  key={point.id}
                  type="button"
                  className={`sidebar-item ${point.status === 'correct' ? 'point-card--correct' : point.status === 'wrong' ? 'point-card--wrong' : ''}`}
                  onClick={() => {
                    if (suppressPointClickRef.current) return;
                    setSelectedPointId(point.id);
                    if (!islandEditMode) {
                      setActiveQuestionState({ islandId: activeIsland!.id, pointId: point.id, selected: [] });
                    }
                  }}
                  onPointerDown={(event) => {
                    if (!islandEditMode || event.button !== 0 || !activeIsland) return;
                    event.stopPropagation();
                    const rect = event.currentTarget.getBoundingClientRect();
                    suppressPointClickRef.current = false;
                    setSelectedPointId(point.id);
                    const nextDrag: Extract<NonNullable<DragState>, { kind: 'point-list' }> = {
                      kind: 'point-list',
                      islandId: activeIsland.id,
                      pointId: point.id,
                      pointerId: event.pointerId,
                      startX: event.clientX,
                      startY: event.clientY,
                      currentX: event.clientX,
                      currentY: event.clientY,
                      grabOffsetX: event.clientX - rect.left,
                      grabOffsetY: event.clientY - rect.top,
                      sourceIndex: activePoints.findIndex((item) => item.id === point.id),
                      insertionIndex: activePoints.findIndex((item) => item.id === point.id),
                      itemWidth: rect.width,
                      itemHeight: rect.height,
                      dragged: false,
                    };
                    dragRef.current = nextDrag;
                    setDragState(nextDrag);
                    event.currentTarget.setPointerCapture(event.pointerId);
                  }}
                  style={
                    dragState?.kind === 'point-list' && dragState.pointId === point.id
                      ? { opacity: 0.15, transform: 'scale(0.98)' }
                      : dragState?.kind === 'point-list'
                        ? (() => {
                            const slotHeight = dragState.itemHeight + 10;
                            const sourceIndex = dragState.sourceIndex;
                            const insertionIndex = dragState.insertionIndex;
                            const index = activePoints.findIndex((item) => item.id === point.id);
                            const shift =
                              insertionIndex > sourceIndex && index > sourceIndex && index < insertionIndex
                                ? -slotHeight
                                : insertionIndex < sourceIndex && index >= insertionIndex && index < sourceIndex
                                  ? slotHeight
                                  : 0;
                            return {
                              transform: shift ? `translateY(${shift}px)` : undefined,
                              transition: 'transform 180ms ease, opacity 180ms ease, box-shadow 180ms ease',
                            };
                          })()
                        : undefined
                  }
                >
                  <span>
                    <strong>{point.title}</strong>
                    <br />
                    <span className="muted">{point.points} Punkte</span>
                  </span>
                  <span>{point.status === 'correct' ? <Check size={16} /> : point.status === 'wrong' ? '✕' : '•'}</span>
                </button>
              ))}
            </div>
            {dragState?.kind === 'point-list' ? (
              <div
                aria-hidden="true"
                style={{
                  position: 'fixed',
                  left: dragState.currentX - dragState.grabOffsetX,
                  top: dragState.currentY - dragState.grabOffsetY,
                  width: dragState.itemWidth,
                  pointerEvents: 'none',
                  zIndex: 80,
                  transform: 'scale(1.02)',
                }}
              >
                <div className="sidebar-item" style={{ boxShadow: '0 16px 40px rgba(15, 23, 42, 0.22)', opacity: 0.98 }}>
                  <span>
                    <strong>{activePoints.find((item) => item.id === dragState.pointId)?.title}</strong>
                    <br />
                    <span className="muted">
                      {activePoints.find((item) => item.id === dragState.pointId)?.points ?? 0} Punkte
                    </span>
                  </span>
                  <span>•</span>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <Modal
        open={Boolean(activeQuestionState && selectedIsland)}
        title="Fragepunkt"
        onClose={() => setActiveQuestionState(null)}
        wide
      >
        {activeQuestionState && selectedIsland ? (
          <QuestionDialog
            island={selectedIsland}
            point={selectedIsland.points.find((item) => item.id === activeQuestionState.pointId)!}
            onClose={() => setActiveQuestionState(null)}
            onAnswer={answerPoint}
            editMode={islandEditMode}
            onUpdate={(patch) => updatePoint(selectedIsland.id, activeQuestionState.pointId, patch)}
          />
        ) : null}
      </Modal>

      <Modal open={Boolean(selectedPointId && selectedIsland && islandEditMode)} title="Punkt bearbeiten" onClose={() => setSelectedPointId(null)} wide>
        {selectedIsland && selectedPointId ? (
          <PointEditor
            point={selectedIsland.points.find((item) => item.id === selectedPointId)!}
            onSave={(patch) => updatePoint(selectedIsland.id, selectedPointId, patch)}
            onDelete={() => {
              setActiveQuestionState(null);
              updateIsland(selectedIsland.id, {
                points: selectedIsland.points.filter((item) => item.id !== selectedPointId),
              });
              setSelectedPointId(null);
            }}
          />
        ) : null}
      </Modal>

      <Modal
        open={Boolean(selectedIsland && islandProgress >= 100)}
        title="Insel abgeschlossen"
        onClose={() => undefined}
      >
        {selectedIsland ? (
          <div className="compact-grid">
            <p className="visual-note">
              {selectedIsland.name} ist abgeschlossen. Fortschritt: {islandProgress}%
            </p>
            <div className="row-actions">
              <GameButton onClick={() => setView('world')}>Zurueck zur Weltkarte</GameButton>
              <GameButton variant="secondary" onClick={nextIsland}>
                Naechste Insel
              </GameButton>
            </div>
          </div>
        ) : null}
      </Modal>
    </SectionShell>
  );
}

function QuestionDialog({
  point,
  onAnswer,
  onClose,
  editMode,
  onUpdate,
}: {
  island: QuestIsland;
  point: QuestPoint;
  onAnswer: (result: QuestionStatus) => void;
  onClose: () => void;
  editMode: boolean;
  onUpdate: (patch: Partial<QuestPoint>) => void;
}) {
  const [selected, setSelected] = useState<number[]>([]);
  const correctAnswer = point.correctIndices;

  const toggle = (index: number) => {
    if (!point.multipleCorrect) {
      setSelected([index]);
      return;
    }
    setSelected((prev) => (prev.includes(index) ? prev.filter((item) => item !== index) : [...prev, index]));
  };

  return (
    <div className="compact-grid">
      <div className="hero-strip">
        <span className="floating-tag">{point.title}</span>
        <span className="floating-tag">{point.points} Punkte</span>
      </div>
      <h3>{point.prompt}</h3>
      <div className="answer-grid">
        {point.answers.map((answer, index) => (
          <button key={answer} type="button" className={`answer-button ${selected.includes(index) ? 'answer-button--correct' : ''}`} onClick={() => toggle(index)}>
            <span className="answer-button__label">{String.fromCharCode(65 + index)}</span>
            <strong>{answer}</strong>
          </button>
        ))}
      </div>
      <div className="row-actions">
        <GameButton onClick={() => onAnswer(compareSelections(selected, correctAnswer) ? 'correct' : 'wrong')}>
          Antwort prufen
        </GameButton>
        <GameButton variant="secondary" onClick={() => onAnswer('wrong')}>
          Falsch
        </GameButton>
        <GameButton variant="ghost" onClick={onClose}>
          Abbrechen
        </GameButton>
      </div>
      {editMode ? (
        <div className="compact-grid">
          <h3>Bearbeitung</h3>
          <div className="form-grid">
            <label className="inline-field">
              <span>Titel</span>
              <input value={point.title} onChange={(event) => onUpdate({ title: event.target.value })} />
            </label>
            <label className="inline-field">
              <span>Punkte</span>
              <input type="number" value={point.points} onChange={(event) => onUpdate({ points: Number(event.target.value) })} />
            </label>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function PointEditor({
  point,
  onSave,
  onDelete,
}: {
  point: QuestPoint;
  onSave: (patch: Partial<QuestPoint>) => void;
  onDelete: () => void;
}) {
  const [draft, setDraft] = useState(point);

  return (
    <div className="compact-grid">
      <div className="form-grid">
        <label className="inline-field">
          <span>Titel</span>
          <input value={draft.title} onChange={(event) => setDraft((prev) => ({ ...prev, title: event.target.value }))} />
        </label>
        <label className="inline-field">
          <span>Punkte</span>
          <input
            type="number"
            value={draft.points}
            onChange={(event) => setDraft((prev) => ({ ...prev, points: Number(event.target.value) }))}
          />
        </label>
      </div>
      <label className="inline-field">
        <span>Frage</span>
        <textarea value={draft.prompt} onChange={(event) => setDraft((prev) => ({ ...prev, prompt: event.target.value }))} />
      </label>
      <div className="form-grid">
        {draft.answers.map((answer, index) => (
          <label key={index} className="inline-field">
            <span>Antwort {String.fromCharCode(65 + index)}</span>
            <input
              value={answer}
              onChange={(event) =>
                setDraft((prev) => ({
                  ...prev,
                  answers: prev.answers.map((item, answerIndex) => (answerIndex === index ? event.target.value : item)),
                }))
              }
            />
          </label>
        ))}
      </div>
      <label className="inline-field">
        <span>Richtige Antworten</span>
        <input
          value={draft.correctIndices.join(',')}
          onChange={(event) =>
            setDraft((prev) => ({
              ...prev,
              correctIndices: event.target.value
                .split(',')
                .map((item) => Number(item.trim()))
                .filter((item) => Number.isFinite(item)),
              multipleCorrect: event.target.value.split(',').filter(Boolean).length > 1,
            }))
          }
        />
      </label>
      <div className="row-actions">
        <GameButton onClick={() => onSave(draft)}>
          Speichern
        </GameButton>
        <GameButton variant="danger" onClick={onDelete}>
          Loeschen
        </GameButton>
      </div>
    </div>
  );
}

function compareSelections(left: number[], right: number[]) {
  const a = [...left].sort((x, y) => x - y);
  const b = [...right].sort((x, y) => x - y);
  return a.length === b.length && a.every((value, index) => value === b[index]);
}
