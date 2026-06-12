import { useEffect, useMemo, useState } from 'react';
import { ArrowLeft, Check, CopyPlus, Edit3, Plus, Save, Trash2 } from 'lucide-react';
import GameButton from '@/components/GameButton';
import Modal from '@/components/Modal';
import SectionShell from '@/components/SectionShell';
import { makeSampleKidsPointsQuizGame, makeSamplePointsQuizGame, pointsQuizCategories, pointsQuizQuestionBank } from '@/data/sampleQuestions';
import type {
  PointsQuizBoardCell,
  PointsQuizCategory,
  PointsQuizGame,
  PointsQuizQuestion,
  PointsQuizTeam,
  SavedEntry,
} from '@/types';
import { createId, formatDate, shuffle } from '@/utils/storage';

type PointsQuizPageProps = {
  savedGames: SavedEntry<PointsQuizGame>[];
  onSaveGame: (game: PointsQuizGame) => void;
  onDeleteGame: (id: string) => void;
  onBack: () => void;
};

type ViewMode = 'quick' | 'editor' | 'library';

type QuickConfig = {
  teamCount: number;
  categoriesCount: number;
  questionsPerCategory: number;
  deductionEnabled: boolean;
  timerEnabled: boolean;
  questionSeconds: number;
  difficulty: 'leicht' | 'mittel' | 'schwer' | 'gemischt';
};

const quickTeamNames = ['Team A', 'Team B', 'Team C', 'Team D', 'Team E', 'Team F', 'Team G', 'Team H'];
const quickColors = ['#7dd3fc', '#f9a8d4', '#86efac', '#fde68a', '#c4b5fd', '#fca5a5', '#67e8f9', '#fbcfe8'];

function rebuildBoard(game: PointsQuizGame) {
  const board = game.categories.map((category) =>
    game.questions
      .filter((question) => question.categoryId === category.id)
      .sort((a, b) => a.points - b.points)
      .map((question) => ({
        id: createId('cell'),
        categoryId: category.id,
        questionId: question.id,
        points: question.points,
        used: false,
      })),
  );
  const rows = Math.max(...board.map((cells) => cells.length), 0);
  const normalized = Array.from({ length: rows }, (_, rowIndex) =>
    game.categories.map((category, columnIndex) => {
      const question = game.questions
        .filter((item) => item.categoryId === category.id)
        .sort((a, b) => a.points - b.points)[rowIndex];
      return {
        id: question?.id ?? createId('cell'),
        categoryId: category.id,
        questionId: question?.id ?? '',
        points: question?.points ?? (rowIndex + 1) * 20,
        used: false,
      } satisfies PointsQuizBoardCell;
    }),
  );

  return normalized;
}

function createQuickGame(config: QuickConfig): PointsQuizGame {
  const categories = pointsQuizCategories.slice(0, config.categoriesCount);
  const selectedQuestions: PointsQuizQuestion[] = [];
  categories.forEach((category) => {
    const pool = pointsQuizQuestionBank.filter((question) => question.categoryId === category.id);
    const needed = pool.slice(0, config.questionsPerCategory);
    selectedQuestions.push(...needed);
  });

  const teams: PointsQuizTeam[] = Array.from({ length: config.teamCount }, (_, index) => ({
    id: createId('team'),
    name: quickTeamNames[index] ?? `Team ${index + 1}`,
    score: 0,
    color: quickColors[index % quickColors.length],
    icon: String(index + 1),
  }));

  return {
    id: createId('points-game'),
    name: 'Schnelles Neon-Quiz',
    description: 'Automatisch generiertes Team-Quiz mit Beispiel-Fragen.',
    categories,
    questions: selectedQuestions,
    teams,
    activeTeamIndex: 0,
    board: rebuildBoard({
      id: 'tmp',
      name: 'tmp',
      description: '',
      categories,
      questions: selectedQuestions,
      teams,
      activeTeamIndex: 0,
      board: [],
      settings: {
        deductionEnabled: config.deductionEnabled,
        timerEnabled: config.timerEnabled,
        questionSeconds: config.questionSeconds,
        categoriesCount: config.categoriesCount,
        questionsPerCategory: config.questionsPerCategory,
      },
      status: 'setup',
      currentCellId: null,
      resolvedCount: 0,
      correctCount: 0,
      wrongCount: 0,
    }),
    settings: {
      deductionEnabled: config.deductionEnabled,
      timerEnabled: config.timerEnabled,
      questionSeconds: config.questionSeconds,
      categoriesCount: config.categoriesCount,
      questionsPerCategory: config.questionsPerCategory,
    },
    status: 'playing',
    currentCellId: null,
    resolvedCount: 0,
    correctCount: 0,
    wrongCount: 0,
  };
}

function normalizeGame(game: PointsQuizGame): PointsQuizGame {
  return {
    ...game,
    board: rebuildBoard(game),
  };
}

function compareSelection(a: number[], b: number[]) {
  const left = [...a].sort((x, y) => x - y);
  const right = [...b].sort((x, y) => x - y);
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

export default function PointsQuizPage({ savedGames, onSaveGame, onDeleteGame, onBack }: PointsQuizPageProps) {
  const [view, setView] = useState<ViewMode>('quick');
  const [quickConfig, setQuickConfig] = useState<QuickConfig>({
    teamCount: 3,
    categoriesCount: 5,
    questionsPerCategory: 4,
    deductionEnabled: true,
    timerEnabled: false,
    questionSeconds: 30,
    difficulty: 'gemischt',
  });
  const [activeGame, setActiveGame] = useState<PointsQuizGame | null>(null);
  const [draftGame, setDraftGame] = useState<PointsQuizGame>(() => normalizeGame(makeSampleKidsPointsQuizGame()));
  const [activeCellId, setActiveCellId] = useState<string | null>(null);
  const [selectedAnswers, setSelectedAnswers] = useState<number[]>([]);
  const [lastOutcome, setLastOutcome] = useState<string>('Noch keine Bewertung.');
  const [editingQuestionId, setEditingQuestionId] = useState<string | null>(null);

  const editorQuestion = useMemo(
    () => draftGame.questions.find((question) => question.id === editingQuestionId) ?? null,
    [draftGame.questions, editingQuestionId],
  );

  const currentGame = activeGame ?? draftGame;

  const startQuickGame = () => {
    const game = createQuickGame(quickConfig);
    setActiveGame(game);
    setView('quick');
    setLastOutcome('Quick-Play gestartet.');
  };

  const openSavedForPlay = (game: PointsQuizGame) => {
    setActiveGame(normalizeGame(game));
    setView('quick');
    setLastOutcome(`Gespeichertes Spiel geladen: ${game.name}`);
  };

  const openSavedForEdit = (game: PointsQuizGame) => {
    setDraftGame(normalizeGame(game));
    setView('editor');
    setLastOutcome(`Editor geladen: ${game.name}`);
  };

  const selectCell = (cellId: string) => {
    const cell = currentGame.board.flat().find((item) => item.id === cellId);
    if (!cell || cell.used) return;
    setActiveCellId(cellId);
    setSelectedAnswers([]);
  };

  const activeCell = currentGame.board.flat().find((item) => item.id === activeCellId) ?? null;
  const activeQuestion = activeCell
    ? currentGame.questions.find((question) => question.id === activeCell.questionId) ?? null
    : null;

  const toggleAnswer = (index: number) => {
    if (!activeQuestion) return;
    if (!activeQuestion.multipleCorrect) {
      setSelectedAnswers([index]);
      return;
    }
    setSelectedAnswers((prev) =>
      prev.includes(index) ? prev.filter((item) => item !== index) : [...prev, index],
    );
  };

  const closeQuestion = () => {
    setActiveCellId(null);
    setSelectedAnswers([]);
  };

  const finalizeCell = (result: 'correct' | 'wrong' | 'skip') => {
    if (!activeCell || !activeQuestion || !activeGame) return;

    const nextGame = { ...activeGame };
    nextGame.board = nextGame.board.map((row) =>
      row.map((cell) => (cell.id === activeCell.id ? { ...cell, used: true } : cell)),
    );
    nextGame.resolvedCount += 1;

    const activeTeam = nextGame.teams[nextGame.activeTeamIndex];
    if (result === 'correct') {
      activeTeam.score += activeCell.points;
      nextGame.correctCount += 1;
      setLastOutcome(`${activeTeam.name} gewinnt ${activeCell.points} Punkte.`);
    } else if (result === 'wrong') {
      if (nextGame.settings.deductionEnabled) {
        activeTeam.score -= activeCell.points;
      }
      nextGame.wrongCount += 1;
      setLastOutcome(`${activeTeam.name} verliert die Runde.`);
    } else {
      setLastOutcome(`${activeTeam.name} hat die Frage uebersprungen.`);
    }

    nextGame.activeTeamIndex = (nextGame.activeTeamIndex + 1) % nextGame.teams.length;
    const finished = nextGame.board.flat().every((cell) => cell.used);
    nextGame.status = finished ? 'finished' : 'playing';
    nextGame.currentCellId = null;
    setActiveGame(nextGame);
    closeQuestion();
  };

  const evaluateAnswer = () => {
    if (!activeQuestion) return;
    if (compareSelection(selectedAnswers, activeQuestion.correctIndices)) {
      finalizeCell('correct');
    } else {
      finalizeCell('wrong');
    }
  };

  const saveDraft = () => {
    onSaveGame(normalizeGame(draftGame));
    setLastOutcome(`Gespeichert: ${draftGame.name}`);
    setView('library');
  };

  const addCategory = () => {
    const nextCategory: PointsQuizCategory = {
      id: createId('category'),
      name: `Kategorie ${draftGame.categories.length + 1}`,
      color: ['#7dd3fc', '#f9a8d4', '#86efac', '#fde68a', '#c4b5fd'][draftGame.categories.length % 5],
    };
    setDraftGame((prev) => ({ ...prev, categories: [...prev.categories, nextCategory] }));
  };

  const addQuestionToCategory = (categoryId: string) => {
    const firstQuestion = pointsQuizQuestionBank.find((question) => question.categoryId === categoryId);
    const newQuestion: PointsQuizQuestion = {
      id: createId('question'),
      categoryId,
      prompt: 'Neue Frage',
      answers: ['Antwort A', 'Antwort B', 'Antwort C', 'Antwort D'],
      correctIndices: [0],
      multipleCorrect: false,
      explanation: '',
      difficulty: 'mittel',
      points: 20,
    };
    setDraftGame((prev) => ({
      ...prev,
      questions: [...prev.questions, firstQuestion ? { ...firstQuestion, id: newQuestion.id, categoryId } : newQuestion],
    }));
    setEditingQuestionId(newQuestion.id);
  };

  const updateQuestion = (updated: PointsQuizQuestion) => {
    setDraftGame((prev) => ({
      ...prev,
      questions: prev.questions.some((question) => question.id === updated.id)
        ? prev.questions.map((question) => (question.id === updated.id ? updated : question))
        : [...prev.questions, updated],
    }));
  };

  const removeQuestion = (questionId: string) => {
    setDraftGame((prev) => ({ ...prev, questions: prev.questions.filter((question) => question.id !== questionId) }));
    if (editingQuestionId === questionId) {
      setEditingQuestionId(null);
    }
  };

  const addTeam = () => {
    setDraftGame((prev) => ({
      ...prev,
      teams: [
        ...prev.teams,
        {
          id: createId('team'),
          name: `Team ${prev.teams.length + 1}`,
          score: 0,
          color: quickColors[prev.teams.length % quickColors.length],
          icon: String(prev.teams.length + 1),
        },
      ],
    }));
  };

  const deleteCategory = (categoryId: string) => {
    setDraftGame((prev) => ({
      ...prev,
      categories: prev.categories.filter((category) => category.id !== categoryId),
      questions: prev.questions.filter((question) => question.categoryId !== categoryId),
    }));
  };

  const currentWinner = useMemo(() => {
    if (!activeGame || activeGame.status !== 'finished') return [];
    const topScore = Math.max(...activeGame.teams.map((team) => team.score));
    return activeGame.teams.filter((team) => team.score === topScore);
  }, [activeGame]);

  const renderBoard = () => (
    <div className="board-grid glass panel-block">
      <div className="board-table">
        {currentGame.categories.map((category) => (
          <div key={category.id} className="board-header glass" style={{ boxShadow: 'none' }}>
            {category.name}
          </div>
        ))}
        {currentGame.board.map((row) =>
          row.map((cell) => (
            <button
              key={cell.id}
              type="button"
              className={`board-cell glass ${cell.used ? 'board-cell--used' : ''} ${cell.id === activeCellId ? 'board-cell--selected' : ''}`}
              onClick={() => selectCell(cell.id)}
            >
              {cell.used ? <Check size={18} /> : <span>{cell.points}</span>}
            </button>
          )),
        )}
      </div>
    </div>
  );

  return (
    <SectionShell
      eyebrow="Spielmodus 2"
      title="Punkte-Quiz"
      action={
        <div className="row-actions">
          <GameButton variant="secondary" onClick={() => setView('quick')}>
            Schnelles Spiel
          </GameButton>
          <GameButton variant="secondary" onClick={() => setView('editor')}>
            Eigene Spiele
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
      <div className="compact-grid">
        <div className="glass panel-block">
          <div className="hero-strip">
            <span className="floating-tag">Status: {currentGame.status}</span>
            <span className="floating-tag">Aktives Team: {currentGame.teams[currentGame.activeTeamIndex]?.name ?? 'n/a'}</span>
            <span className="floating-tag">{lastOutcome}</span>
          </div>

          {view === 'quick' ? (
            <div className="compact-grid">
              <div className="form-grid">
                <label className="inline-field">
                  <span>Teamanzahl</span>
                  <input
                    type="number"
                    min={2}
                    max={8}
                    value={quickConfig.teamCount}
                    onChange={(event) => setQuickConfig((prev) => ({ ...prev, teamCount: clampNumber(event.target.value, 2, 8) }))}
                  />
                </label>
                <label className="inline-field">
                  <span>Kategorien</span>
                  <input
                    type="number"
                    min={3}
                    max={6}
                    value={quickConfig.categoriesCount}
                    onChange={(event) => setQuickConfig((prev) => ({ ...prev, categoriesCount: clampNumber(event.target.value, 3, 6) }))}
                  />
                </label>
                <label className="inline-field">
                  <span>Fragen pro Kategorie</span>
                  <input
                    type="number"
                    min={3}
                    max={6}
                    value={quickConfig.questionsPerCategory}
                    onChange={(event) => setQuickConfig((prev) => ({ ...prev, questionsPerCategory: clampNumber(event.target.value, 3, 6) }))}
                  />
                </label>
                <label className="inline-field">
                  <span>Falsche Antwort abziehen</span>
                  <select
                    value={quickConfig.deductionEnabled ? 'yes' : 'no'}
                    onChange={(event) => setQuickConfig((prev) => ({ ...prev, deductionEnabled: event.target.value === 'yes' }))}
                  >
                    <option value="yes">Ja</option>
                    <option value="no">Nein</option>
                  </select>
                </label>
              </div>
              <div className="row-actions">
                <GameButton icon={<PlayIcon />} onClick={startQuickGame}>
                  Spiel starten
                </GameButton>
                <GameButton variant="secondary" onClick={() => setActiveGame(normalizeGame(makeSampleKidsPointsQuizGame()))}>
                  Kinder-Quiz laden
                </GameButton>
                <GameButton variant="secondary" onClick={() => setActiveGame(normalizeGame(makeSamplePointsQuizGame()))}>
                  Standard-Beispiel
                </GameButton>
              </div>
            </div>
          ) : null}

          {view === 'editor' ? (
            <div className="compact-grid">
              <div className="form-grid">
                <label className="inline-field">
                  <span>Spielname</span>
                  <input
                    value={draftGame.name}
                    onChange={(event) => setDraftGame((prev) => ({ ...prev, name: event.target.value }))}
                  />
                </label>
                <label className="inline-field">
                  <span>Beschreibung</span>
                  <input
                    value={draftGame.description}
                    onChange={(event) => setDraftGame((prev) => ({ ...prev, description: event.target.value }))}
                  />
                </label>
              </div>
              <div className="row-actions">
                <GameButton icon={<Plus size={18} />} onClick={addCategory}>
                  Kategorie hinzufuegen
                </GameButton>
                <GameButton icon={<Plus size={18} />} variant="secondary" onClick={addTeam}>
                  Team hinzufuegen
                </GameButton>
                <GameButton icon={<Save size={18} />} onClick={saveDraft}>
                  Speichern
                </GameButton>
              </div>
              <div className="two-column-grid">
                {draftGame.categories.map((category) => {
                  const categoryQuestions = draftGame.questions.filter((question) => question.categoryId === category.id);
                  return (
                    <div key={category.id} className="glass panel-block">
                      <div className="row-actions" style={{ justifyContent: 'space-between' }}>
                        <input
                          value={category.name}
                          onChange={(event) =>
                            setDraftGame((prev) => ({
                              ...prev,
                              categories: prev.categories.map((item) =>
                                item.id === category.id ? { ...item, name: event.target.value } : item,
                              ),
                            }))
                          }
                        />
                        <GameButton variant="ghost" size="sm" onClick={() => deleteCategory(category.id)}>
                          <Trash2 size={16} />
                        </GameButton>
                      </div>
                      <div className="stack-list" style={{ marginTop: 12 }}>
                        {categoryQuestions.map((question) => (
                          <article key={question.id} className="list-card" style={{ display: 'grid' }}>
                            <strong>{question.prompt}</strong>
                            <span>{question.points} Punkte</span>
                            <div className="row-actions">
                              <GameButton variant="secondary" size="sm" onClick={() => setEditingQuestionId(question.id)}>
                                <Edit3 size={14} /> Bearbeiten
                              </GameButton>
                              <GameButton variant="ghost" size="sm" onClick={() => removeQuestion(question.id)}>
                                <Trash2 size={14} /> Loeschen
                              </GameButton>
                            </div>
                          </article>
                        ))}
                        <GameButton variant="secondary" size="sm" icon={<Plus size={14} />} onClick={() => addQuestionToCategory(category.id)}>
                          Frage hinzufuegen
                        </GameButton>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null}

          {view === 'library' ? (
            <div className="two-column-grid">
              <div className="glass panel-block">
                <h3>Gespeicherte Spiele</h3>
                <div className="stack-list">
                  {savedGames.map((entry) => (
                    <article key={entry.id} className="list-card" style={{ display: 'grid' }}>
                      <strong>{entry.name}</strong>
                      <span>{formatDate(entry.updatedAt)}</span>
                      <div className="row-actions">
                        <GameButton size="sm" onClick={() => openSavedForPlay(entry.data)}>
                          Spielen
                        </GameButton>
                        <GameButton variant="secondary" size="sm" onClick={() => openSavedForEdit(entry.data)}>
                          Laden
                        </GameButton>
                        <GameButton variant="ghost" size="sm" onClick={() => onDeleteGame(entry.id)}>
                          <Trash2 size={14} />
                        </GameButton>
                        <GameButton variant="ghost" size="sm" onClick={() => onSaveGame({ ...entry.data, id: entry.data.id })}>
                          <CopyPlus size={14} />
                        </GameButton>
                      </div>
                    </article>
                  ))}
                </div>
              </div>
              <div className="glass panel-block">
                <h3>Aktive Sammlung</h3>
                <p className="visual-note">
                  Eigenes Spiel erstellen, laden, speichern oder direkt im Teammodus starten.
                </p>
              </div>
            </div>
          ) : null}
        </div>

        {renderBoard()}

        <div className="two-column-grid">
          <div className="glass panel-block">
            <h3>Teams</h3>
            <div className="team-strip">
              {currentGame.teams.map((team, index) => (
                <article
                  key={team.id}
                  className={`team-card ${index === currentGame.activeTeamIndex ? 'team-card--active' : ''}`}
                  style={{ borderTop: `4px solid ${team.color}` }}
                >
                  <strong>{team.icon} {team.name}</strong>
                  <p className="muted">{team.score} Punkte</p>
                </article>
              ))}
            </div>
          </div>

          <div className="glass panel-block">
            <h3>Status</h3>
            <p className="visual-note">
              {currentGame.status === 'finished'
                ? `Das Spiel ist beendet. Gewinner: ${currentWinner.map((team) => team.name).join(', ')}`
                : 'Waehle ein Feld aus der Punktetafel. Im Dialog kann die Spielleitung die Antwort bewerten.'}
            </p>
            {currentGame.status === 'finished' ? (
              <div className="row-actions">
                <GameButton onClick={() => setActiveGame(null)}>Neues Spiel</GameButton>
                <GameButton variant="secondary" onClick={onBack}>
                  Zurueck zum Menu
                </GameButton>
              </div>
            ) : null}
          </div>
        </div>
      </div>

      <Modal open={Boolean(activeCell && activeQuestion)} title="Frage beantworten" onClose={closeQuestion} wide>
        {activeQuestion ? (
          <div className="compact-grid">
            <div className="hero-strip">
              <span className="floating-tag">Team: {currentGame.teams[currentGame.activeTeamIndex]?.name}</span>
              <span className="floating-tag">Punkte: {activeCell?.points ?? 0}</span>
              <span className="floating-tag">{activeQuestion.difficulty}</span>
            </div>
            <h3>{activeQuestion.prompt}</h3>
            <div className="answer-grid">
              {activeQuestion.answers.map((answer, index) => {
                const selected = selectedAnswers.includes(index);
                return (
                  <button
                    key={answer}
                    type="button"
                    className={`answer-button ${selected ? 'answer-button--correct' : ''}`}
                    onClick={() => toggleAnswer(index)}
                  >
                    <span className="answer-button__label">{String.fromCharCode(65 + index)}</span>
                    <strong>{answer}</strong>
                  </button>
                );
              })}
            </div>
            <div className="row-actions">
              <GameButton onClick={evaluateAnswer}>
                Bewerten
              </GameButton>
              <GameButton variant="secondary" onClick={() => finalizeCell('skip')}>
                Ueberspringen
              </GameButton>
              <GameButton variant="ghost" onClick={closeQuestion}>
                Abbrechen
              </GameButton>
            </div>
          </div>
        ) : null}
      </Modal>

      <Modal open={Boolean(editorQuestion)} title="Frage bearbeiten" onClose={() => setEditingQuestionId(null)} wide>
        {editorQuestion ? (
          <QuestionEditor
            question={editorQuestion}
            categories={draftGame.categories}
            onSave={(updated) => {
              updateQuestion(updated);
              setEditingQuestionId(null);
            }}
            onCancel={() => setEditingQuestionId(null)}
          />
        ) : null}
      </Modal>
    </SectionShell>
  );
}

function clampNumber(value: string, min: number, max: number) {
  const parsed = Number(value);
  if (Number.isNaN(parsed)) return min;
  return Math.min(max, Math.max(min, parsed));
}

function PlayIcon() {
  return <ArrowLeft size={18} style={{ transform: 'rotate(180deg)' }} />;
}

function QuestionEditor({
  question,
  categories,
  onSave,
  onCancel,
}: {
  question: PointsQuizQuestion;
  categories: PointsQuizCategory[];
  onSave: (question: PointsQuizQuestion) => void;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState(question);

  useEffect(() => {
    setDraft(question);
  }, [question]);

  return (
    <div className="compact-grid">
      <div className="form-grid">
        <label className="inline-field">
          <span>Kategorie</span>
          <select value={draft.categoryId} onChange={(event) => setDraft((prev) => ({ ...prev, categoryId: event.target.value }))}>
            {categories.map((category) => (
              <option key={category.id} value={category.id}>
                {category.name}
              </option>
            ))}
          </select>
        </label>
        <label className="inline-field">
          <span>Punkte</span>
          <input
            type="number"
            value={draft.points}
            onChange={(event) => setDraft((prev) => ({ ...prev, points: clampNumber(event.target.value, 10, 1000) }))}
          />
        </label>
      </div>
      <label className="inline-field">
        <span>Fragetext</span>
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
          onChange={(event) => {
            const values = event.target.value
              .split(',')
              .map((item) => Number(item.trim()))
              .filter((value) => Number.isFinite(value) && value >= 0 && value <= 3);
            setDraft((prev) => ({
              ...prev,
              correctIndices: values,
              multipleCorrect: values.length > 1,
            }));
          }}
        />
      </label>
      <label className="inline-field">
        <span>Erklaerung</span>
        <textarea value={draft.explanation ?? ''} onChange={(event) => setDraft((prev) => ({ ...prev, explanation: event.target.value }))} />
      </label>
      <div className="row-actions">
        <GameButton onClick={() => onSave(draft)}>
          Speichern
        </GameButton>
        <GameButton variant="secondary" onClick={onCancel}>
          Abbrechen
        </GameButton>
      </div>
    </div>
  );
}
