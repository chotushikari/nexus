$ErrorActionPreference = "Stop"

$ProjectId = "piyush-507208"
$Region = "us-central1"
$Service = "nexus-api"
$Image = "$Region-docker.pkg.dev/$ProjectId/nexus/api:latest"
$RuntimeServiceAccount = "nexus-api-runtime@$ProjectId.iam.gserviceaccount.com"

gcloud builds submit apps/api --config apps/api/cloudbuild.yaml --project $ProjectId

gcloud run deploy $Service `
  --image $Image `
  --region $Region `
  --project $ProjectId `
  --service-account $RuntimeServiceAccount `
  --min-instances 0 `
  --max-instances 3 `
  --concurrency 10 `
  --timeout 300 `
  --set-env-vars "ENVIRONMENT=cloud,GOOGLE_CLOUD_PROJECT=$ProjectId,GOOGLE_CLOUD_LOCATION=$Region,FIRESTORE_DATABASE=nexus-db,GEMINI_MODEL=gemini-3.5-flash,GEMINI_MODEL_LITE=gemini-3.5-flash-lite,DEMO_MODE=true" `
  --allow-unauthenticated

