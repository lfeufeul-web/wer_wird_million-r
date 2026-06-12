/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { MapTemplate, Quest } from "./types";

export const MAP_TEMPLATES: MapTemplate[] = [
  {
    id: "forest",
    name: "Forest",
    image: "https://lh3.googleusercontent.com/aida-public/AB6AXuDujYeVOIbjHkAOgwaWo1l43M9PdBhcp_Tz6uDLFmu1NLafK-PLEkC0vDKCFYzUpw17iVPc1y1fNeT3T4pAgWo36rp32MPs9EyRZ6vq0AGXhjdiu8UNMtjLz-iHYZSbjaJmYlcLOYLxuNBeaFNRs71Owjo0nU-EsMadqASfgzM9aAA80sQBA43I2uUuuKNx-GjueU5h1sMIU3JZeBVLChZmMcCBmVjAMS5svthvFwu5w1sGbNcCkcUezc_YJQIDcqTxCc-tocuH8GzV",
    thumb: "https://lh3.googleusercontent.com/aida-public/AB6AXuBTcuFhaVyrnAjuj_r_kr_cxRweOkYjEIR8fXpnWOvYabk8hAbquOtRQZTK3epGbrHs-GiUvX4b1T8liaIaI5Pb2qzvKn0WUjDESIxdSoCw1VS8GMq6qcr7fwMex5nIWMPk2URzOhb5v2HiPgyuZsFFtkX77OHQiSASyENvUflrReMvby4bp6eIZKF-6CDuyAOrwdgCjocZcX0V10vyRYMtiRvUlY1UhJL5LM_D4TLAxL4T8YgX3GixMA5e-sh1ciE3lJaQcnkzWbo7",
    description: "Ein dichter, detailreicher Zauberwald mit Geheimpfaden, einer Brücke und Campingplatz."
  },
  {
    id: "city",
    name: "City",
    image: "https://lh3.googleusercontent.com/aida-public/AB6AXuDfspSd7Wwcnu0lQLSC2lVPDEYSdC4-GTaDqJlMm6PMNBKbcRWouRydApMgIvd7l0m1xYRC7grM44qJTuz5xjKZ-Itgc-eSBQYIMc0uNzD9HXlqRsmDkUUjw_DRjsiNDcq0_NkBeTBbjheWT4uV5DQp4CYtDc1EpASZr12rH5kRYNqFj2LiuwDYfknWs3GVHnEpMFzkNNxyxbb_pEI4zM3Jj7xbIWlgxNhaGzDEyhTeO0i4Ho9njkOXRkf6HQmvVt4PWvh3E2FwmV96",
    thumb: "https://lh3.googleusercontent.com/aida-public/AB6AXuDfspSd7Wwcnu0lQLSC2lVPDEYSdC4-GTaDqJlMm6PMNBKbcRWouRydApMgIvd7l0m1xYRC7grM44qJTuz5xjKZ-Itgc-eSBQYIMc0uNzD9HXlqRsmDkUUjw_DRjsiNDcq0_NkBeTBbjheWT4uV5DQp4CYtDc1EpASZr12rH5kRYNqFj2LiuwDYfknWs3GVHnEpMFzkNNxyxbb_pEI4zM3Jj7xbIWlgxNhaGzDEyhTeO0i4Ho9njkOXRkf6HQmvVt4PWvh3E2FwmV96",
    description: "Ein lebendiges, isometrisches Stadtviertel mit geometrischen Straßen und Mini-Fahrzeugen."
  },
  {
    id: "school",
    name: "School",
    image: "https://lh3.googleusercontent.com/aida-public/AB6AXuCj9Z2m4Wtvdm5wtPsCQhSh9WHcLV1H1Jp6u78BHSaDfPJMeRhAgQ47gUl0_k38dR7BhUe2MFs8wvzOK7zfMC9GhuoIR2MI-ckFINWZ8QF7n1qtSYSt8BJuPXpykiH3xYZXETYRvNZVlhtgLIJSzneLMFiAviPxwta5y8kjXQS9UdVkt8bf90MgL-gk1MJ-oRp-m4DEyJAVKKLY8cpFebn5uNiSzvxKG4CvMRAwNlVpJchuZP1zD-0e1lM1oXE7uD0rr0I05mJJaQKp",
    thumb: "https://lh3.googleusercontent.com/aida-public/AB6AXuCj9Z2m4Wtvdm5wtPsCQhSh9WHcLV1H1Jp6u78BHSaDfPJMeRhAgQ47gUl0_k38dR7BhUe2MFs8wvzOK7zfMC9GhuoIR2MI-ckFINWZ8QF7n1qtSYSt8BJuPXpykiH3xYZXETYRvNZVlhtgLIJSzneLMFiAviPxwta5y8kjXQS9UdVkt8bf90MgL-gk1MJ-oRp-m4DEyJAVKKLY8cpFebn5uNiSzvxKG4CvMRAwNlVpJchuZP1zD-0e1lM1oXE7uD0rr0I05mJJaQKp",
    description: "Der bunte Flur einer modernen Highschool mit Spinden und pädagogischem Design."
  },
  {
    id: "island",
    name: "Island",
    image: "https://lh3.googleusercontent.com/aida-public/AB6AXuAnMFOtEWgoQd_gWa1JCGtRu3UkhFGFmwIE13RyrMq_z1WJFk5iPmxXA0fuenUr5gII1TC0hZlrhtq0MNnZr1UilKXa7qXIAMwr0VikaAKR4-vZYkJVrKkuY8chkqKckM9oTuY3Dlfmm9yjgLQJujKk6A77Vt-dllCinmSzKkcYO1hcoy2POmwawi3KuctCrdTstDH5uGN6OGIgRl_XZF6DgtkSTiA3eY7EC-oaozyj-DPh13JXdjwJaqBRaIYPhNLhO1FGjodv3xDz",
    thumb: "https://lh3.googleusercontent.com/aida-public/AB6AXuAnMFOtEWgoQd_gWa1JCGtRu3UkhFGFmwIE13RyrMq_z1WJFk5iPmxXA0fuenUr5gII1TC0hZlrhtq0MNnZr1UilKXa7qXIAMwr0VikaAKR4-vZYkJVrKkuY8chkqKckM9oTuY3Dlfmm9yjgLQJujKk6A77Vt-dllCinmSzKkcYO1hcoy2POmwawi3KuctCrdTstDH5uGN6OGIgRl_XZF6DgtkSTiA3eY7EC-oaozyj-DPh13JXdjwJaqBRaIYPhNLhO1FGjodv3xDz",
    description: "Eine abenteuerliche Insel mit paradiesischer Naturkulisse und ruhigen Palmenrändern."
  }
];

export const DEFAULT_QUESTS: Quest[] = [
  {
    id: "island-escape",
    title: "Island Escape",
    level: "Level 1: The Beach",
    mapTemplateId: "forest",
    points: [
      {
        id: "pt-1",
        x: 38.3,
        y: 41.5,
        question: "Was ist das Hauptmerkmal dieser mystischen Waldregion?",
        answers: ["Kakaobäume", "Fruchtbare Vulkanerde", "Dichte Nadelwälder & Teiche", "Unterseeische Riffe"],
        correctAnswerIndex: 2
      },
      {
        id: "pt-2",
        x: 54.0,
        y: 53.0,
        question: "Welches magische Reittier haust der Legende nach am Ufer des glitzernden Teichs?",
        answers: ["Der Smaragdfrosch", "Der Moos-Hirsch", "Die Nebel-Schildkröte", "Das Silberfischchen"],
        correctAnswerIndex: 0
      },
      {
        id: "pt-3",
        x: 73.5,
        y: 59.5,
        question: "Wer hat das rote Abenteurerzelt im östlichen Außenposten aufgeschlagen?",
        answers: ["Die QuestMapper Gilde", "Eine Gruppe Naturforscher", "Verlorene Holzfäller", "Ein mürrischer Einsiedler"],
        correctAnswerIndex: 1
      },
      {
        id: "pt-4",
        x: 82.0,
        y: 47.0,
        question: "Durch welches Element ist der Teich gegenüber dem Pfad an der Ostgrenze gesichert?",
        answers: ["Ein massives Holztor", "Einen antiken Steinkreis", "Eine charmante Bogenbrücke", "Einen tiefen Graben"],
        correctAnswerIndex: 2
      }
    ]
  },
  {
    id: "city-patrol",
    title: "Metropolis Mission",
    level: "Level 2: City Streets",
    mapTemplateId: "city",
    points: [
      {
        id: "pt-c1",
        x: 30.0,
        y: 45.0,
        question: "Welcher Architekturstil prägt die isometrischen Hochhäuser im Stadtzentrum?",
        answers: ["Klassizismus", "Brutalistisch-Modern", "Retro-Futuristisch", "Gotisch"],
        correctAnswerIndex: 2
      },
      {
        id: "pt-c2",
        x: 65.0,
        y: 35.0,
        question: "Wie viele Grünstreifen säumen die Hauptverkehrsstraßen dieser Miniaturstadt?",
        answers: ["Keine, alles ist asphaltiert", "Jede Straße ist doppelspurig begrünt", "Einige ausgewählte Alleenhälften", "Nur der zentrale Stadtpark"],
        correctAnswerIndex: 1
      }
    ]
  },
  {
    id: "school-detective",
    title: "Akademie Rätsel",
    level: "Level 1: Flurgang",
    mapTemplateId: "school",
    points: [
      {
        id: "pt-s1",
        x: 40.0,
        y: 50.0,
        question: "Welche Farbe hat das geöffnete Spind, in dem die Questnotiz versteckt ist?",
        answers: ["Signalgelb", "Himmelblau", "Türkis", "Pastellrosa"],
        correctAnswerIndex: 2
      },
      {
        id: "pt-s2",
        x: 72.0,
        y: 60.0,
        question: "Welches Fachgebiet wird auf dem Hauptplakat neben dem Trinkbrunnen beworben?",
        answers: ["Astronomie-AG", "Chemie-Laborversuche", "Mathematik-Zirkel", "Kunst & Freihandzeichnen"],
        correctAnswerIndex: 0
      }
    ]
  }
];
