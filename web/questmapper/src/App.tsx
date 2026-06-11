import { Home, Layers3, Settings, Trophy } from 'lucide-react';
import AnimatedBackground from '@/components/AnimatedBackground';
import GameButton from '@/components/GameButton';
import { makeSampleKidsPointsQuizGame, makeSamplePointsQuizGame, sampleQuestWorlds, wwmSampleQuestions } from '@/data/sampleQuestions';
import PointsQuizPage from '@/features/points-quiz/PointsQuizPage';
import QuestPathPage from '@/features/quest-path/QuestPathPage';
import WwmPage from '@/features/wwm/WwmPage';
import { useLocalStorageState } from '@/hooks/useLocalStorageState';
import MainMenu from '@/pages/MainMenu';
import SavesPage from '@/pages/SavesPage';
import SettingsPage from '@/pages/SettingsPage';
import type { AppSection, AppSettings, PointsQuizGame, QuestPathWorld, SavedEntry } from '@/types';
import { STORAGE_KEYS, createId } from '@/utils/storage';

const defaultSettings: AppSettings = {
  soundEnabled: true,
  motionEnabled: true,
  autosave: true,
  accent: '#22d3ee',
};

function toSavedEntry<T extends { id: string; name: string }>(data: T): SavedEntry<T> {
  return {
    id: createId('save'),
    name: data.name,
    updatedAt: new Date().toISOString(),
    data,
  };
}

export default function App() {
  const [section, setSection] = useLocalStorageState<AppSection>('questmapper.section.v1', 'menu');
  const [settings, setSettings] = useLocalStorageState<AppSettings>(STORAGE_KEYS.appSettings, defaultSettings);
  const [savedPointsGames, setSavedPointsGames] = useLocalStorageState<SavedEntry<PointsQuizGame>[]>(
    STORAGE_KEYS.pointsGames,
    [toSavedEntry(makeSampleKidsPointsQuizGame()), toSavedEntry(makeSamplePointsQuizGame())],
  );
  const [savedQuestWorlds, setSavedQuestWorlds] = useLocalStorageState<SavedEntry<QuestPathWorld>[]>(
    STORAGE_KEYS.questWorlds,
    sampleQuestWorlds.map((world) => toSavedEntry(world)),
  );

  const handleSavePointsGame = (game: PointsQuizGame) => {
    setSavedPointsGames((prev) => [toSavedEntry(game), ...prev]);
  };

  const handleDeletePointsGame = (id: string) => {
    setSavedPointsGames((prev) => prev.filter((entry) => entry.id !== id));
  };

  const handleSaveQuestWorld = (world: QuestPathWorld) => {
    setSavedQuestWorlds((prev) => [toSavedEntry(world), ...prev]);
  };

  const handleDeleteQuestWorld = (id: string) => {
    setSavedQuestWorlds((prev) => prev.filter((entry) => entry.id !== id));
  };

  const clearSaves = () => {
    setSavedPointsGames([]);
    setSavedQuestWorlds([]);
  };

  const renderSection = () => {
    switch (section) {
      case 'settings':
        return <SettingsPage settings={settings} onChange={setSettings} onBack={() => setSection('menu')} />;
      case 'saves':
        return (
          <SavesPage
            pointsGames={savedPointsGames}
            questWorlds={savedQuestWorlds}
            onBack={() => setSection('menu')}
            onClear={clearSaves}
          />
        );
      case 'wwm':
        return <WwmPage onBack={() => setSection('menu')} />;
      case 'points':
        return (
          <PointsQuizPage
            savedGames={savedPointsGames}
            onSaveGame={handleSavePointsGame}
            onDeleteGame={handleDeletePointsGame}
            onBack={() => setSection('menu')}
          />
        );
      case 'quest':
        return (
          <QuestPathPage
            savedWorlds={savedQuestWorlds}
            onSaveWorld={handleSaveQuestWorld}
            onDeleteWorld={handleDeleteQuestWorld}
            onBack={() => setSection('menu')}
          />
        );
      case 'menu':
      default:
        return (
          <MainMenu
            onNavigate={setSection}
            worldCount={savedQuestWorlds.length}
            pointsCount={savedPointsGames.length}
          />
        );
    }
  };

  return (
    <div className="app-shell" style={{ ['--accent' as string]: settings.accent }}>
      <AnimatedBackground />

      <header className="app-shell__nav">
        <div className="app-shell__brand">
          <span className="brand-mark">
            <Trophy size={18} />
          </span>
          <div>
            <div>Neon Quiz Forge</div>
            <div className="small-label">{wwmSampleQuestions.length} WWM-Fragen sofort spielbar</div>
          </div>
        </div>

        <div className="app-shell__nav-actions">
          <GameButton variant={section === 'menu' ? 'primary' : 'ghost'} size="sm" icon={<Home size={16} />} onClick={() => setSection('menu')}>
            Startseite
          </GameButton>
          <GameButton variant={section === 'saves' ? 'primary' : 'ghost'} size="sm" icon={<Layers3 size={16} />} onClick={() => setSection('saves')}>
            Spielstaende
          </GameButton>
          <GameButton variant={section === 'settings' ? 'primary' : 'ghost'} size="sm" icon={<Settings size={16} />} onClick={() => setSection('settings')}>
            Einstellungen
          </GameButton>
        </div>
      </header>

      {renderSection()}
    </div>
  );
}
