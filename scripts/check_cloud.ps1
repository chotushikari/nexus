$ErrorActionPreference = "Stop"

$ProjectId = "piyush-507208"
$Region = "us-central1"

gcloud services list --enabled --project $ProjectId `
  --filter="config.name:(run.googleapis.com OR cloudbuild.googleapis.com OR artifactregistry.googleapis.com OR secretmanager.googleapis.com OR firestore.googleapis.com OR aiplatform.googleapis.com OR generativelanguage.googleapis.com OR modelarmor.googleapis.com OR pubsub.googleapis.com)" `
  --format="table(config.name)"

gcloud firestore databases list --project $ProjectId --format="table(name,locationId,type)"
gcloud artifacts repositories list --project $ProjectId --location $Region --format="table(name,format)"
gcloud iam service-accounts describe "nexus-api-runtime@$ProjectId.iam.gserviceaccount.com" --project $ProjectId --format="table(email,displayName)"

