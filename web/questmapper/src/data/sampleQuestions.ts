import {
  type PointsQuizCategory,
  type PointsQuizGame,
  type PointsQuizQuestion,
  type QuestIsland,
  type QuestPathWorld,
  type QuestPoint,
  type WwmQuestion,
} from '@/types';
import { createId } from '@/utils/storage';

export const wwmSampleQuestions: WwmQuestion[] = [
  {
    id: 'wwm-01',
    amount: 50,
    category: 'Allgemeinwissen',
    difficulty: 'leicht',
    prompt: 'Welche Farbe ergibt Blau und Gelb?',
    answers: ['Grun', 'Lila', 'Orange', 'Braun'],
    correctIndex: 0,
    fact: 'Blau und Gelb mischen sich zu Grun.',
  },
  {
    id: 'wwm-02',
    amount: 100,
    category: 'Natur',
    difficulty: 'leicht',
    prompt: 'Wie nennt man Wasser in fester Form?',
    answers: ['Dampf', 'Eis', 'Nebel', 'Regen'],
    correctIndex: 1,
  },
  {
    id: 'wwm-03',
    amount: 200,
    category: 'Geschichte',
    difficulty: 'leicht',
    prompt: 'Welches Land ist fur seine Pyramiden bekannt?',
    answers: ['Portugal', 'Agypten', 'Finnland', 'Kanada'],
    correctIndex: 1,
  },
  {
    id: 'wwm-04',
    amount: 300,
    category: 'Technik',
    difficulty: 'leicht',
    prompt: 'Wofur steht CPU bei einem Computer?',
    answers: ['Central Processing Unit', 'Color Print Utility', 'Core Power Upload', 'Central Program Update'],
    correctIndex: 0,
  },
  {
    id: 'wwm-05',
    amount: 500,
    category: 'Sport',
    difficulty: 'mittel',
    prompt: 'Wie viele Spieler stehen beim Fussball pro Team auf dem Feld?',
    answers: ['9', '10', '11', '12'],
    correctIndex: 2,
    fact: 'Pro Team sind 11 Spieler gleichzeitig aktiv.',
  },
  {
    id: 'wwm-06',
    amount: 1_000,
    category: 'Musik',
    difficulty: 'mittel',
    prompt: 'Wie viele Halbtone hat eine klassische westliche Oktave?',
    answers: ['8', '10', '12', '14'],
    correctIndex: 2,
  },
  {
    id: 'wwm-07',
    amount: 2_000,
    category: 'Geografie',
    difficulty: 'mittel',
    prompt: 'Welche Stadt liegt in Deutschland?',
    answers: ['Lyon', 'Lissabon', 'Leipzig', 'Toulouse'],
    correctIndex: 2,
  },
  {
    id: 'wwm-08',
    amount: 4_000,
    category: 'Logik',
    difficulty: 'mittel',
    prompt: 'Welche Zahl folgt logisch auf 2, 4, 8, 16?',
    answers: ['18', '24', '32', '64'],
    correctIndex: 2,
  },
  {
    id: 'wwm-09',
    amount: 8_000,
    category: 'Wissenschaft',
    difficulty: 'schwer',
    prompt: 'Woraus besteht Wasser chemisch?',
    answers: ['H2O', 'CO2', 'NaCl', 'O2'],
    correctIndex: 0,
  },
  {
    id: 'wwm-10',
    amount: 16_000,
    category: 'Kultur',
    difficulty: 'schwer',
    prompt: 'Welcher Autor schrieb "Die Verwandlung"?',
    answers: ['Franz Kafka', 'Johann Goethe', 'Thomas Mann', 'Bertolt Brecht'],
    correctIndex: 0,
  },
  {
    id: 'wwm-11',
    amount: 32_000,
    category: 'Geschichte',
    difficulty: 'schwer',
    prompt: 'In welchem Jahr fiel die Berliner Mauer?',
    answers: ['1987', '1989', '1991', '1995'],
    correctIndex: 1,
  },
  {
    id: 'wwm-12',
    amount: 64_000,
    category: 'Technik',
    difficulty: 'schwer',
    prompt: 'Welche Einheit misst elektrische Leistung?',
    answers: ['Volt', 'Ampere', 'Watt', 'Ohm'],
    correctIndex: 2,
  },
  {
    id: 'wwm-13',
    amount: 125_000,
    category: 'Weltall',
    difficulty: 'schwer',
    prompt: 'Wie heisst der rote Planet?',
    answers: ['Mars', 'Venus', 'Jupiter', 'Saturn'],
    correctIndex: 0,
  },
  {
    id: 'wwm-14',
    amount: 500_000,
    category: 'Denken',
    difficulty: 'schwer',
    prompt: 'Was ist die Wurzel aus 144?',
    answers: ['10', '11', '12', '13'],
    correctIndex: 2,
  },
  {
    id: 'wwm-15',
    amount: 1_000_000,
    category: 'Finale',
    difficulty: 'schwer',
    prompt: 'Welche Aussage trifft am ehesten zu?',
    answers: ['Die Erde ist eine Scheibe', 'Der Mond ist aus Kaese', 'Das Licht ist schneller als Schall', 'Der Himmel ist grun'],
    correctIndex: 2,
    fact: 'Licht ist schneller als Schall.',
  },
];

const baseCategoryPalette = ['#7dd3fc', '#f9a8d4', '#86efac', '#fde68a', '#c4b5fd', '#fca5a5'];

export const pointsQuizCategories: PointsQuizCategory[] = [
  { id: 'cat-geschichte', name: 'Geschichte', color: baseCategoryPalette[0] },
  { id: 'cat-natur', name: 'Natur', color: baseCategoryPalette[1] },
  { id: 'cat-technik', name: 'Technik', color: baseCategoryPalette[2] },
  { id: 'cat-popkultur', name: 'Popkultur', color: baseCategoryPalette[3] },
  { id: 'cat-logik', name: 'Logik', color: baseCategoryPalette[4] },
  { id: 'cat-sport', name: 'Sport', color: baseCategoryPalette[5] },
];

function makePointsQuestion(
  categoryId: string,
  points: number,
  prompt: string,
  answers: string[],
  correctIndices: number[],
  difficulty: PointsQuizQuestion['difficulty'],
  explanation?: string,
): PointsQuizQuestion {
  return {
    id: createId('pq'),
    categoryId,
    prompt,
    answers,
    correctIndices,
    multipleCorrect: correctIndices.length > 1,
    explanation,
    difficulty,
    points,
  };
}

export const pointsQuizQuestionBank: PointsQuizQuestion[] = [
  makePointsQuestion('cat-geschichte', 20, 'Wann begann der Zweite Weltkrieg?', ['1914', '1939', '1945', '1961'], [1], 'leicht'),
  makePointsQuestion('cat-geschichte', 40, 'Wer war Alexander der Grosse?', ['Ein Romer', 'Ein griechischer Herrscher', 'Ein Astronaut', 'Ein Komponist'], [1], 'leicht'),
  makePointsQuestion('cat-geschichte', 60, 'Welche Stadt war ein Zentrum der Renaissance?', ['Florenz', 'Oslo', 'Reykjavik', 'Dublin'], [0], 'mittel'),
  makePointsQuestion('cat-geschichte', 80, 'Welche Dynastie regierte lange in China?', ['Habsburger', 'Ming', 'Capetinger', 'Wittelsbacher'], [1], 'mittel'),
  makePointsQuestion('cat-natur', 20, 'Welches Tier legt Eier?', ['Hund', 'Katze', 'Ente', 'Pferd'], [2], 'leicht'),
  makePointsQuestion('cat-natur', 40, 'Welche Pflanze braucht Licht fur Photosynthese?', ['Stein', 'Farn', 'Metall', 'Wolke'], [1], 'leicht'),
  makePointsQuestion('cat-natur', 60, 'Welche Jahreszeit folgt auf den Winter?', ['Herbst', 'Fruhling', 'Sommer', 'Monsun'], [1], 'leicht'),
  makePointsQuestion('cat-natur', 80, 'Wie heisst der Prozess, wenn Wasser zu Dampf wird?', ['Sublimation', 'Verdunstung', 'Kondensation', 'Kristallisation'], [1], 'mittel'),
  makePointsQuestion('cat-technik', 20, 'Wofur steht USB?', ['Universal Serial Bus', 'United System Base', 'Ultra Speed Bridge', 'User Sync Byte'], [0], 'leicht'),
  makePointsQuestion('cat-technik', 40, 'Was ist ein Browser?', ['Ein Kochtopf', 'Ein Webprogramm', 'Ein LKW', 'Eine Tastatur'], [1], 'leicht'),
  makePointsQuestion('cat-technik', 60, 'Welche Datei-Endung hat eine TypeScript-Datei?', ['.py', '.tsx', '.ts', '.go'], [2], 'mittel'),
  makePointsQuestion('cat-technik', 80, 'Was bedeutet RAM?', ['Read Access Memory', 'Random Access Memory', 'Rapid Action Mode', 'Root Array Map'], [1], 'mittel'),
  makePointsQuestion('cat-popkultur', 20, 'Welche Farbe hat oft ein klassischer Superhelden-Umhang?', ['Braun', 'Grau', 'Rot', 'Gros'], [2], 'leicht'),
  makePointsQuestion('cat-popkultur', 40, 'Wie nennt man eine kurze Bildschirmszene nach dem Abspann?', ['Intro', 'Post-Credit-Scene', 'Loop', 'Creditsafe'], [1], 'leicht'),
  makePointsQuestion('cat-popkultur', 60, 'Was ist ein Meme?', ['Ein Rezept', 'Ein Online-Humorformat', 'Ein Werkzeug', 'Eine Sprache'], [1], 'mittel'),
  makePointsQuestion('cat-popkultur', 80, 'Welche Serie ist fur ihre gelbe Familie bekannt?', ['Die Simpsons', 'Friends', 'Dark', 'Seinfeld'], [0], 'mittel'),
  makePointsQuestion('cat-logik', 20, 'Welche Zahl ist gerade?', ['3', '5', '8', '11'], [2], 'leicht'),
  makePointsQuestion('cat-logik', 40, 'Welche Form hat 3 Seiten?', ['Kreis', 'Dreieck', 'Quadrat', 'Oval'], [1], 'leicht'),
  makePointsQuestion('cat-logik', 60, 'Welche Aussage ist logisch wahr?', ['Alle Fische fliegen', 'Manche Katzen sind Tiere', 'Alle Zahlen sind rosa', 'Keiner lacht je'], [1], 'mittel'),
  makePointsQuestion('cat-logik', 80, 'Welche Abfolge passt am besten: A, C, E, G, ...?', ['H', 'I', 'J', 'K'], [0], 'schwer'),
  makePointsQuestion('cat-sport', 20, 'Welcher Ball wird beim Fussball benutzt?', ['Ovaler Ball', 'Runder Ball', 'Wuerfel', 'Frisbee'], [1], 'leicht'),
  makePointsQuestion('cat-sport', 40, 'Wie heisst der Sport auf dem Eis mit dem Puck?', ['Eishockey', 'Handball', 'Rugby', 'Tennis'], [0], 'leicht'),
  makePointsQuestion('cat-sport', 60, 'Wie viele Ringe hat das olympische Symbol?', ['3', '4', '5', '6'], [2], 'mittel'),
  makePointsQuestion('cat-sport', 80, 'Was ist ein Marathon grob?', ['100 m Sprint', 'Ein sehr langer Lauf', 'Schwimmen', 'Radfahren'], [1], 'mittel'),
];

const kidQuizCategories: PointsQuizCategory[] = [
  { id: 'kid-cat-tiere', name: 'Tiere', color: '#93c5fd' },
  { id: 'kid-cat-schule', name: 'Schule', color: '#f9a8d4' },
  { id: 'kid-cat-natur', name: 'Natur', color: '#86efac' },
  { id: 'kid-cat-zahlen', name: 'Zahlen', color: '#fde68a' },
];

function makeKidQuizQuestion(
  categoryId: string,
  points: number,
  prompt: string,
  answers: string[],
  correctIndices: number[],
  explanation?: string,
): PointsQuizQuestion {
  return {
    id: createId('kid-question'),
    categoryId,
    prompt,
    answers,
    correctIndices,
    multipleCorrect: correctIndices.length > 1,
    explanation,
    difficulty: points <= 20 ? 'leicht' : points <= 40 ? 'mittel' : 'schwer',
    points,
  };
}

const kidQuizQuestions: PointsQuizQuestion[] = [
  makeKidQuizQuestion('kid-cat-tiere', 10, 'Welches Tier miaut?', ['Hund', 'Katze', 'Huhn', 'Fisch'], [1], 'Katzen machen oft ein Miauen.'),
  makeKidQuizQuestion('kid-cat-tiere', 20, 'Welches Tier kann fliegen?', ['Kuh', 'Elefant', 'Adler', 'Schaf'], [2], 'Adler sind grosse Vögel und können fliegen.'),
  makeKidQuizQuestion('kid-cat-tiere', 30, 'Welches Tier lebt im Wasser?', ['Delfin', 'Pferd', 'Löwe', 'Hase'], [0], 'Delfine leben im Meer.'),
  makeKidQuizQuestion('kid-cat-tiere', 40, 'Welches Tier hat einen Rüssel?', ['Maus', 'Elefant', 'Igel', 'Ente'], [1], 'Der Elefant hat einen langen Rüssel.'),
  makeKidQuizQuestion('kid-cat-schule', 10, 'Was brauchst du zum Schreiben?', ['Ball', 'Stift', 'Löffel', 'Kissen'], [1], 'Mit einem Stift kann man schreiben.'),
  makeKidQuizQuestion('kid-cat-schule', 20, 'Welche Farbe hat oft ein Heft aus der Schule?', ['Blau', 'Grün', 'Rot', 'Alle können vorkommen'], [3], 'Hefte gibt es in vielen Farben.'),
  makeKidQuizQuestion('kid-cat-schule', 30, 'Was macht man in der Pause?', ['Schlafen', 'Spielen', 'Tauchen', 'Kochen'], [1], 'In der Pause wird oft gespielt und gerannt.'),
  makeKidQuizQuestion('kid-cat-schule', 40, 'Womit liest man ein Buch?', ['Mit den Händen', 'Mit den Augen', 'Mit den Füßen', 'Mit dem Ohr'], [1], 'Gelesen wird mit den Augen.'),
  makeKidQuizQuestion('kid-cat-natur', 10, 'Welche Jahreszeit ist oft warm?', ['Winter', 'Sommer', 'Herbst', 'Nebel'], [1], 'Im Sommer ist es oft warm.'),
  makeKidQuizQuestion('kid-cat-natur', 20, 'Was brauchen Pflanzen zum Wachsen?', ['Licht und Wasser', 'Schokolade', 'Sand nur', 'Trommeln'], [0], 'Pflanzen brauchen Licht und Wasser.'),
  makeKidQuizQuestion('kid-cat-natur', 30, 'Welche Farbe hat Gras meistens?', ['Blau', 'Grün', 'Lila', 'Orange'], [1], 'Gras ist meistens grün.'),
  makeKidQuizQuestion('kid-cat-natur', 40, 'Was fällt bei Regen vom Himmel?', ['Steine', 'Wasser', 'Sterne', 'Blätter'], [1], 'Regen besteht aus Wasser.'),
  makeKidQuizQuestion('kid-cat-zahlen', 10, 'Wie viel ist 2 + 1?', ['1', '2', '3', '4'], [2], 'Zwei plus eins ist drei.'),
  makeKidQuizQuestion('kid-cat-zahlen', 20, 'Welche Zahl kommt nach 5?', ['3', '4', '6', '8'], [2], 'Nach 5 kommt 6.'),
  makeKidQuizQuestion('kid-cat-zahlen', 30, 'Wie viel ist 4 + 4?', ['6', '7', '8', '9'], [2], 'Vier plus vier ist acht.'),
  makeKidQuizQuestion('kid-cat-zahlen', 40, 'Welche Zahl ist größer?', ['9', '2', '1', '0'], [0], '9 ist größer als 2, 1 und 0.'),
];

function createPointsBoard(questions: PointsQuizQuestion[], categories: PointsQuizCategory[]) {
  const perCategory = new Map<string, PointsQuizQuestion[]>();
  categories.forEach((cat) => {
    perCategory.set(
      cat.id,
      questions.filter((question) => question.categoryId === cat.id).sort((a, b) => a.points - b.points),
    );
  });

  const maxRows = Math.max(...Array.from(perCategory.values()).map((list) => list.length));
  const board = Array.from({ length: maxRows }, (_, rowIndex) =>
    categories.map((category) => {
      const question = perCategory.get(category.id)?.[rowIndex];
      return {
        id: question?.id ?? createId('cell'),
        categoryId: category.id,
        questionId: question?.id ?? createId('missing'),
        points: question?.points ?? (rowIndex + 1) * 20,
        used: false,
      };
    }),
  );

  return board;
}

export function makeSamplePointsQuizGame(): PointsQuizGame {
  const categories = pointsQuizCategories.slice(0, 5);
  const questions = pointsQuizQuestionBank.filter((question) => categories.some((category) => category.id === question.categoryId));

  return {
    id: createId('points-game'),
    name: 'Neon Quiz Arena',
    description: 'Ein schnelles, spielbares Team-Quiz mit Beispieldaten.',
    categories,
    questions,
    teams: [
      { id: createId('team'), name: 'Team A', score: 0, color: '#7dd3fc', icon: 'A' },
      { id: createId('team'), name: 'Team B', score: 0, color: '#f9a8d4', icon: 'B' },
      { id: createId('team'), name: 'Team C', score: 0, color: '#86efac', icon: 'C' },
    ],
    activeTeamIndex: 0,
    board: createPointsBoard(questions, categories),
    settings: {
      deductionEnabled: true,
      timerEnabled: false,
      questionSeconds: 30,
      categoriesCount: categories.length,
      questionsPerCategory: 4,
    },
    status: 'setup',
    currentCellId: null,
    resolvedCount: 0,
    correctCount: 0,
    wrongCount: 0,
  };
}

export function makeSampleKidsPointsQuizGame(): PointsQuizGame {
  const categories = kidQuizCategories;
  const questions = kidQuizQuestions;

  return {
    id: createId('points-game'),
    name: 'Mein Grundschul-Quiz',
    description: 'Ein freundliches Punkte-Quiz mit einfachen Fragen für Kinder.',
    categories,
    questions,
    teams: [
      { id: createId('team'), name: 'Team Sonne', score: 0, color: '#93c5fd', icon: 'S' },
      { id: createId('team'), name: 'Team Regenbogen', score: 0, color: '#f9a8d4', icon: 'R' },
      { id: createId('team'), name: 'Team Stern', score: 0, color: '#86efac', icon: 'T' },
    ],
    activeTeamIndex: 0,
    board: createPointsBoard(questions, categories),
    settings: {
      deductionEnabled: false,
      timerEnabled: false,
      questionSeconds: 30,
      categoriesCount: categories.length,
      questionsPerCategory: 4,
    },
    status: 'setup',
    currentCellId: null,
    resolvedCount: 0,
    correctCount: 0,
    wrongCount: 0,
  };
}

function makeQuestPoint(title: string, prompt: string, points: number, x: number, y: number, correctIndices: number[]): QuestPoint {
  return {
    id: createId('qp'),
    title,
    prompt,
    answers: ['Antwort A', 'Antwort B', 'Antwort C', 'Antwort D'],
    correctIndices,
    multipleCorrect: correctIndices.length > 1,
    explanation: 'Beispiel-Erklarung fur den Fragen-Pfad.',
    points,
    x,
    y,
    status: 'open',
  };
}

function makeIsland(
  name: string,
  description: string,
  x: number,
  y: number,
  style: QuestIsland['style'],
  mapStyle: QuestIsland['mapStyle'],
  points: QuestPoint[],
): QuestIsland {
  return {
    id: createId('island'),
    name,
    description,
    x,
    y,
    style,
    mapStyle,
    completed: false,
    progress: 0,
    points,
  };
}

export const sampleQuestWorld: QuestPathWorld = {
  id: createId('world'),
  name: 'Neon Archipel',
  description: 'Eine schwebende Abenteuerwelt aus Inseln, Karten und Fragepunkten.',
  theme: 'fantasy',
  scale: 1,
  offsetX: 0,
  offsetY: 0,
  islands: [
    makeIsland('Waldinsel', 'Der ruhige Startpunkt mit leichtem Einstieg.', -180, -40, 'waldinsel', 'waldkarte', [
      makeQuestPoint('Moospfad', 'Welche Farbe passt zu frischem Moos?', 10, 16, 18, [1]),
      makeQuestPoint('Tannenlicht', 'Welche Aussage ist richtig?', 20, 38, 34, [2]),
      makeQuestPoint('Quellstein', 'Welches Tier lebt am ehesten im Wald?', 30, 62, 20, [0]),
    ]),
    makeIsland('Feuerinsel', 'Lava, Hitze und mutige Fragen.', 40, -10, 'feuerinsel', 'vulkan', [
      makeQuestPoint('Glutpfad', 'Was ist heisser: Lava oder Schnee?', 20, 18, 24, [0]),
      makeQuestPoint('Funkenrat', 'Welche Zahl passt?', 30, 49, 50, [3]),
      makeQuestPoint('Aschenstern', 'Wofur steht "CPU"?', 40, 72, 26, [2]),
    ]),
    makeIsland('Ozeaninsel', 'Sanfte Wellen, aber tiefe Fragen.', 210, 55, 'wasserinsel', 'ozean', [
      makeQuestPoint('Korallenbucht', 'Welche Einheit misst elektrische Leistung?', 30, 20, 28, [2]),
      makeQuestPoint('Wellenruf', 'Wie viele Ozeane gibt es meist in der modernen Einteilung?', 40, 44, 18, [1]),
      makeQuestPoint('Tiefenlicht', 'Welche Farbe entsteht aus Blau und Gelb?', 50, 66, 44, [0]),
      makeQuestPoint('Strudelpunkt', 'Wie viele Seiten hat ein Dreieck?', 60, 78, 24, [1]),
    ]),
  ],
};

export const sampleQuestWorlds: QuestPathWorld[] = [sampleQuestWorld];
