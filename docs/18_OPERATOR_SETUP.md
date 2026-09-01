# Operator Setup Checklist

Use this checklist before Sprint 2 cloud verification. Do not paste secrets into chat.

## 1. Google Cloud Project

Create or choose one Google Cloud project for NEXUS.

Needed from you:
- project ID
- preferred region, recommended `us-central1`
- whether billing is enabled

## 2. Firestore

Create a Firestore database.

Needed from you:
- database name, recommended `nexus-db`
- confirmation that local Application Default Credentials can access it

## 3. Gemini / ADK Auth

Choose one auth path:

- Gemini API key mode for fastest local demo
- Google Cloud / Vertex-style auth for stronger cloud story

Needed from you:
- auth mode choice
- confirmation that the secret is stored in `.env.local` or Secret Manager

## 4. Local Dependency Install

Sprint 2 needs permission to install Python packages from [pyproject.toml](/D:/Nexus/apps/api/pyproject.toml).

Command I will ask to run:

```powershell
python -m pip install -e "apps/api[dev]"
```

## 5. Cloud Deployment

Sprint 6 needs:

- permission to run `gcloud`
- Artifact Registry or Cloud Build availability
- Cloud Run deploy permission
- Secret Manager permission

## Never Share

- service account private keys
- API key values
- `.env.local`
- credential JSON files

