# HearBeat Frontend

Next.js visualization workspace for the HearBeat audio analysis engine.

## Development

```bash
npm install
npm run dev
```

Open `http://localhost:3000`.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | Backend API URL (e.g. `https://your-backend.run.app`) |

Copy `.env.example` to `.env.local` for local development.

## Deploy to Vercel

### Option 1: Vercel CLI

```bash
npm i -g vercel
vercel
```

### Option 2: Git Integration

1. Push to GitHub/GitLab/Bitbucket
2. Import project at [vercel.com/new](https://vercel.com/new)
3. Set `NEXT_PUBLIC_API_URL` in Project Settings > Environment Variables
4. Deploy

### Option 3: Vercel CLI (production)

```bash
vercel --prod
```

### Environment Variables on Vercel

In Project Settings > Environment Variables:

| Name | Value | Environment |
|------|-------|-------------|
| `NEXT_PUBLIC_API_URL` | `https://your-gcp-backend.run.app` | Production, Preview |

### Custom Domain

1. Go to Project Settings > Domains
2. Add your domain (e.g. `hearbeat.app`)
3. Configure DNS as instructed by Vercel
