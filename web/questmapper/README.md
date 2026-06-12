# QuestMapper Web

React/Vite frontend for the QuestMapper editor and play experience.

This is the first safe migration step away from the Python/Flet UI for the highly interactive map editor. The existing Flet app remains deployed as `wer-wird-millionaer`; this frontend is deployed separately as the `questmapper-web` static site in `render.yaml`.

## Local development

```bash
npm install
npm run dev
```

The app starts on `http://localhost:3000`.

## Production build

```bash
npm run build
```

Render publishes the generated `dist` folder as a static site.
