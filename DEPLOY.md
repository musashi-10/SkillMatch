# GitHub → Render

## 1. Push to GitHub

```bash
git init
git add .
git status
git commit -m "SkillMatch"
```

Create an empty repo on GitHub, then:

```bash
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git branch -M main
git push -u origin main
```

Do not commit `.env` or `*.db` (see `.gitignore`).

## 2. Deploy on Render

1. [render.com](https://render.com) → sign in with GitHub.
2. **New → Blueprint** → choose this repository → confirm `render.yaml`.
3. After deploy, open **Environment** and set **`APP_URL`** to your live URL (e.g. `https://skillmatch-xxxx.onrender.com`).
4. Optional: **SMTP_*** for email (see `.env.example`).

The app is at **`/`** on your Render URL. Health check: **`/docs`**.

### Free tier

- Cold start after idle (~30–60s).
- SQLite under `/app/data` is **ephemeral** unless you add a **paid** disk mounted at `/app/data`.

## Local Docker

```bash
docker build -t skillmatch .
docker run -p 8000:8000 -e JWT_SECRET=dev-secret skillmatch
```

Open `http://localhost:8000/`.

## Rebuild jobs DB locally

```bash
python create_db.py --force
```
