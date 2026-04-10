# KiteFuel — Frontend

Vue 3 single-page application built with **Vite** and **Tailwind CSS**.

## Stack
- [Vue 3](https://vuejs.org/) (Composition API)
- [Vite](https://vitejs.dev/) (dev server + bundler)
- [Tailwind CSS v4](https://tailwindcss.com/) via `@tailwindcss/vite`

## Getting Started

```bash
npm install
npm run dev        # dev server → http://localhost:5173
npm run build      # production build → dist/
npm run preview    # preview production build
```

## Project Structure

```
src/
├── App.vue        # Root component
├── main.js        # App entry point
└── style.css      # Tailwind CSS import
vite.config.js     # Vite config — Vue plugin + Tailwind plugin
Dockerfile         # Container image definition
```

## Environment Variables

Prefix all frontend env vars with `VITE_` so Vite exposes them to the browser:

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | Backend base URL (default: `http://localhost:8000`) |

## Notes
- No component library — plain Tailwind utility classes only.
- This scaffold contains no business logic or API calls yet.
