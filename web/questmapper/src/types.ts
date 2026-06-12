/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export interface QuestPoint {
  id: string;
  x: number; // percentage coordinate on map template (0-100)
  y: number; // percentage coordinate on map template (0-100)
  question: string;
  answers: string[]; // Options a, b, c, d
  correctAnswerIndex: number; // Index 0-3
}

export interface MapTemplate {
  id: string;
  name: string;
  image: string; // The high-res display image for editing and play
  thumb: string; // The side nav preview thumbnail
  description: string;
}

export interface Quest {
  id: string;
  title: string;
  level: string;
  mapTemplateId: string;
  points: QuestPoint[];
}

export interface GameSession {
  questId: string;
  activePointId: string | null;
  answers: Record<string, number>; // Maps pointId -> selected index
  completed: boolean;
}
