# Exchange Dashboard Frontend

React + TypeScript + Vite приложение для управления криптообменником.

## 🚀 Деплой на Vercel

### Автоматический деплой

1. Подключите репозиторий к Vercel
2. Выберите папку `front` как Root Directory
3. Vercel автоматически определит настройки из `vercel.json`

### Ручной деплой

```bash
cd front
npm install
npx vercel --prod
```

## 🔧 Environment Variables

В Vercel Dashboard добавьте переменную:

- `VITE_API_BASE_URL` = `https://gleb.onrender.com`

## 📁 Структура проекта

```
front/
├── src/
│   ├── components/     # React компоненты
│   ├── config/        # Конфигурация (API URL)
│   └── vite-env.d.ts  # TypeScript типы для Vite
├── .env.development   # Dev переменные
├── .env.production    # Prod переменные
├── vercel.json        # Конфиг для Vercel
└── package.json
```

## 🛠 Локальная разработка

```bash
npm install
npm run dev    # localhost:5173
```

## 📦 Сборка

```bash
npm run build
npm run preview  # Превью билда
```

## 🔗 API Integration

Приложение работает с backend: https://gleb.onrender.com

Автоматически использует:

- `http://127.0.0.1:8000` в development
- `https://gleb.onrender.com` в production
