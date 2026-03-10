# 6:28 Zónázó Vonat 🚂 — AWS Deployment

A fáradt, unott, de büszke 6:28-as zónázó vonat chatbotja.
**Ez a repo az AWS App Runner verzió. A Railway verzió külön repoban van.**

---

## Folder structure

```
628AWS/
├── Dockerfile          ← AWS App Runner uses this
├── main.py
├── requirements.txt
└── static/
    └── index.html
```

---

## Deployment steps

### 1. GitHub repo létrehozása

```bash
git init
git add .
git commit -m "628 AWS deployment"
git remote add origin https://github.com/FELHASZNALONEVED/628-vonat-aws.git
git push -u origin main
```

### 2. AWS App Runner service létrehozása

1. Menj az [AWS Console](https://console.aws.amazon.com) → **App Runner**
2. **Create service**
3. Source: **Source code repository** → connect GitHub → válaszd ki a repót
4. Branch: `main`
5. Deployment trigger: **Automatic** (minden push-ra auto-deploy)
6. Build settings:
   - Runtime: **Python 3**
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port 8080`
   - Port: `8080`
7. Service name: `628-vonat`
8. **Create & deploy**

### 3. Environment variables beállítása

App Runner Console → a service-ed → **Configuration** fül → **Environment variables**:

```
OPENAI_API_KEY      = sk-...az_openai_api_kulcsod...
CERTIFICATE_CODE    = 628VAC   (vagy amit szeretnél)
```

### 4. Custom domain (628.hu) bekötése

**A) Ha át tudod irányítani a DNS-t Route 53-ra (ajánlott):**

1. AWS Console → **Route 53** → **Hosted zones** → **Create hosted zone**
   - Domain: `628.hu`
2. Route 53 ad 4 db NS (nameserver) rekordot — ezeket add meg a domainregisztrátornál (ahol a 628.hu-t vetted)
3. App Runner → service → **Custom domains** fül → **Link domain** → `628.hu`
4. App Runner automatikusan konfigurálja a DNS rekordokat és az SSL tanúsítványt ✅

**B) Ha a DNS marad a jelenlegi regisztrátornál:**

1. App Runner → service → **Custom domains** → **Link domain** → `628.hu`
2. App Runner ad CNAME rekordokat — ezeket kézzel add hozzá a regisztrátornál
3. Várj 24-48 órát a propagációra

---

## Local futtatás (Docker)

```bash
docker build -t 628-vonat .
docker run -p 8080:8080 \
  -e OPENAI_API_KEY=sk-... \
  -e CERTIFICATE_CODE=628VAC \
  628-vonat
```

Majd nyisd meg: http://localhost:8080

## Local futtatás (Python)

```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...
export CERTIFICATE_CODE=628VAC
uvicorn main:app --reload --port 8080
```

---

## Különbség a Railway verziótól

| | Railway | AWS |
|---|---|---|
| Config fájl | `Procfile`, `railway.toml` | `Dockerfile` |
| `index.html` helye | repo gyökér | `static/` mappa |
| Port | `$PORT` (Railway adja) | `8080` (fix) |
