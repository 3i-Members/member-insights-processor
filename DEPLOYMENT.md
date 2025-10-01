# Deployment Guide

This guide covers deploying the Member Insights Processor to Google Cloud Platform using Cloud Run, Cloud Run Jobs, and GKE.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Docker Testing](#local-docker-testing)
- [Google Cloud Run Deployment](#google-cloud-run-deployment)
- [Google Cloud Run Jobs](#google-cloud-run-jobs)
- [Google Kubernetes Engine (GKE)](#google-kubernetes-engine-gke)
- [Secrets Management](#secrets-management)
- [Monitoring and Logging](#monitoring-and-logging)

## Prerequisites

1. **Google Cloud Project**: Set up a GCP project with billing enabled
2. **gcloud CLI**: Install and authenticate
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```
3. **Enable APIs**:
   ```bash
   gcloud services enable \
     cloudbuild.googleapis.com \
     run.googleapis.com \
     secretmanager.googleapis.com \
     bigquery.googleapis.com \
     storage.googleapis.com
   ```

## Local Docker Testing

### Build the Docker Image

```bash
# Build the production image
docker build -t member-insights-processor:latest --target production .

# Or build the development image
docker build -t member-insights-processor:dev --target application .
```

### Test Locally

```bash
# Run with environment file
docker run --rm \
  --env-file .env \
  member-insights-processor:latest \
  python src/main.py --validate

# Run a test processing job
docker run --rm \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  member-insights-processor:latest \
  python src/main.py --contact-id CNT-ABC123 --dry-run
```

### Interactive Shell

```bash
docker run --rm -it \
  --env-file .env \
  member-insights-processor:latest \
  /bin/bash
```

## Google Cloud Run Deployment

Cloud Run is ideal for API-based or on-demand processing.

### 1. Store Secrets in Secret Manager

```bash
# Create secrets
echo -n "your-anthropic-key" | gcloud secrets create anthropic-api-key --data-file=-
echo -n "your-openai-key" | gcloud secrets create openai-api-key --data-file=-
echo -n "your-supabase-url" | gcloud secrets create supabase-url --data-file=-
echo -n "your-supabase-key" | gcloud secrets create supabase-service-role-key --data-file=-

# Upload GCP service account credentials
gcloud secrets create gcp-credentials --data-file=/path/to/service-account.json
```

### 2. Build and Push to Container Registry

```bash
# Set variables
export PROJECT_ID=$(gcloud config get-value project)
export SERVICE_NAME="member-insights-processor"
export REGION="us-central1"
export IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}:latest"

# Build and push
gcloud builds submit --tag ${IMAGE_NAME}

# Or use Docker directly
docker build -t ${IMAGE_NAME} --target production .
docker push ${IMAGE_NAME}
```

### 3. Deploy to Cloud Run

```bash
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME} \
  --platform managed \
  --region ${REGION} \
  --memory 4Gi \
  --cpu 2 \
  --timeout 3600 \
  --concurrency 1 \
  --max-instances 10 \
  --no-allow-unauthenticated \
  --set-env-vars "PYTHONUNBUFFERED=1,OPENAI_MAX_CONCURRENT=5" \
  --set-secrets "ANTHROPIC_API_KEY=anthropic-api-key:latest,OPENAI_API_KEY=openai-api-key:latest,SUPABASE_URL=supabase-url:latest,SUPABASE_SERVICE_ROLE_KEY=supabase-service-role-key:latest" \
  --set-secrets "GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp-credentials=gcp-credentials:latest" \
  --service-account ${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com
```

### 4. Test the Deployment

```bash
# Get the service URL
SERVICE_URL=$(gcloud run services describe ${SERVICE_NAME} \
  --platform managed \
  --region ${REGION} \
  --format 'value(status.url)')

# Invoke validation
gcloud run services proxy ${SERVICE_NAME} \
  --region ${REGION} &

curl http://localhost:8080/validate
```

## Google Cloud Run Jobs

**Recommended for production batch processing** - Cloud Run Jobs are perfect for scheduled or on-demand batch workloads.

### 1. Create Cloud Run Job

```bash
gcloud run jobs create ${SERVICE_NAME}-job \
  --image ${IMAGE_NAME} \
  --region ${REGION} \
  --memory 4Gi \
  --cpu 2 \
  --max-retries 3 \
  --task-timeout 3600 \
  --parallelism 1 \
  --tasks 1 \
  --set-env-vars "PYTHONUNBUFFERED=1,OPENAI_MAX_CONCURRENT=5" \
  --set-secrets "ANTHROPIC_API_KEY=anthropic-api-key:latest,OPENAI_API_KEY=openai-api-key:latest,SUPABASE_URL=supabase-url:latest,SUPABASE_SERVICE_ROLE_KEY=supabase-service-role-key:latest" \
  --set-secrets "GOOGLE_APPLICATION_CREDENTIALS=/secrets/gcp-credentials=gcp-credentials:latest" \
  --service-account ${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com \
  --command python \
  --args src/main.py,--parallel,--max-concurrent-contacts,5,--limit,100
```

### 2. Execute the Job

```bash
# Execute immediately
gcloud run jobs execute ${SERVICE_NAME}-job \
  --region ${REGION} \
  --wait

# Execute with custom arguments
gcloud run jobs execute ${SERVICE_NAME}-job \
  --region ${REGION} \
  --args="src/main.py,--contact-id,CNT-ABC123" \
  --wait
```

### 3. Schedule with Cloud Scheduler

```bash
# Create a scheduler job to run daily at 2 AM
gcloud scheduler jobs create http ${SERVICE_NAME}-daily \
  --schedule="0 2 * * *" \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${SERVICE_NAME}-job:run" \
  --http-method POST \
  --oauth-service-account-email ${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com \
  --location ${REGION}
```

### 4. View Job Executions and Logs

```bash
# List executions
gcloud run jobs executions list \
  --job ${SERVICE_NAME}-job \
  --region ${REGION}

# View logs for a specific execution
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=${SERVICE_NAME}-job" \
  --limit 50 \
  --format json
```

## Google Kubernetes Engine (GKE)

For advanced orchestration needs, deploy to GKE.

### 1. Create GKE Cluster

```bash
gcloud container clusters create member-insights-cluster \
  --region ${REGION} \
  --num-nodes 3 \
  --machine-type n1-standard-4 \
  --enable-autoscaling \
  --min-nodes 1 \
  --max-nodes 10 \
  --enable-stackdriver-kubernetes
```

### 2. Configure Workload Identity

```bash
# Create Kubernetes service account
kubectl create serviceaccount ${SERVICE_NAME}-sa

# Bind to GCP service account
gcloud iam service-accounts add-iam-policy-binding \
  ${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:${PROJECT_ID}.svc.id.goog[default/${SERVICE_NAME}-sa]"

# Annotate Kubernetes service account
kubectl annotate serviceaccount ${SERVICE_NAME}-sa \
  iam.gke.io/gcp-service-account=${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com
```

### 3. Create Kubernetes Resources

Create `k8s/deployment.yaml`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: member-insights-secrets
type: Opaque
stringData:
  ANTHROPIC_API_KEY: "your-key"
  OPENAI_API_KEY: "your-key"
  SUPABASE_URL: "your-url"
  SUPABASE_SERVICE_ROLE_KEY: "your-key"
---
apiVersion: batch/v1
kind: CronJob
metadata:
  name: member-insights-processor
spec:
  schedule: "0 2 * * *"  # Daily at 2 AM
  jobTemplate:
    spec:
      template:
        metadata:
          labels:
            app: member-insights-processor
        spec:
          serviceAccountName: member-insights-processor-sa
          containers:
          - name: processor
            image: gcr.io/YOUR_PROJECT_ID/member-insights-processor:latest
            command: ["python", "src/main.py"]
            args: ["--parallel", "--max-concurrent-contacts", "5", "--limit", "100"]
            env:
            - name: PYTHONUNBUFFERED
              value: "1"
            - name: OPENAI_MAX_CONCURRENT
              value: "5"
            envFrom:
            - secretRef:
                name: member-insights-secrets
            resources:
              requests:
                memory: "4Gi"
                cpu: "2"
              limits:
                memory: "8Gi"
                cpu: "4"
            volumeMounts:
            - name: logs
              mountPath: /app/logs
          volumes:
          - name: logs
            emptyDir: {}
          restartPolicy: OnFailure
```

Apply the configuration:

```bash
kubectl apply -f k8s/deployment.yaml
```

### 4. Manual Job Execution

```bash
# Create a one-time job from the CronJob
kubectl create job --from=cronjob/member-insights-processor manual-run-$(date +%s)

# View job status
kubectl get jobs

# View logs
kubectl logs -f job/manual-run-XXXXX
```

## Secrets Management

### Using Google Secret Manager

Best practice is to use Secret Manager for all sensitive credentials:

```bash
# Grant service account access to secrets
for SECRET in anthropic-api-key openai-api-key supabase-url supabase-service-role-key gcp-credentials; do
  gcloud secrets add-iam-policy-binding ${SECRET} \
    --member="serviceAccount:${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done
```

### Service Account Permissions

Create a service account with appropriate permissions:

```bash
# Create service account
gcloud iam service-accounts create ${SERVICE_NAME} \
  --display-name "Member Insights Processor"

# Grant BigQuery permissions
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataViewer"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

# Grant Cloud Storage permissions (for GCS traces)
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectCreator"
```

## Monitoring and Logging

### Cloud Logging

```bash
# View recent logs
gcloud logging read "resource.type=cloud_run_job" \
  --limit 50 \
  --format json

# Filter by service
gcloud logging read "resource.labels.service_name=${SERVICE_NAME}" \
  --limit 50

# Stream logs in real-time
gcloud logging tail "resource.type=cloud_run_job"
```

### Cloud Monitoring

Create custom metrics and alerts:

```bash
# Create alert policy for job failures
gcloud alpha monitoring policies create \
  --notification-channels=CHANNEL_ID \
  --display-name="${SERVICE_NAME} Job Failures" \
  --condition-display-name="Job Failed" \
  --condition-threshold-value=1 \
  --condition-threshold-duration=60s \
  --condition-filter='resource.type="cloud_run_job" AND metric.type="run.googleapis.com/job/completed_execution_count" AND metric.labels.result="failed"'
```

### Trace Collection to GCS

The processor can write LLM traces to GCS when configured in `config/config.yaml`:

```yaml
debug:
  enable_debug_mode: false
  llm_trace:
    enabled: true
    remote_output_uri: "gs://your-bucket/llm_traces"
```

## Resource Sizing Recommendations

### Development/Testing
- **Memory**: 2Gi
- **CPU**: 1
- **Timeout**: 1800s (30 min)
- **Concurrency**: 1

### Production
- **Memory**: 4-8Gi
- **CPU**: 2-4
- **Timeout**: 3600s (60 min)
- **Concurrency**: 1-5 (depending on workload)
- **Max Instances**: 10

### High Volume Processing
- Use Cloud Run Jobs with multiple tasks
- Set `--parallelism` to 5-10
- Monitor BigQuery quotas and API rate limits

## Cost Optimization

1. **Use Cloud Run Jobs** instead of always-on Cloud Run services
2. **Schedule jobs** during off-peak hours
3. **Set max instances** to control parallel execution costs
4. **Use preemptible GKE nodes** for non-critical processing
5. **Monitor OpenAI/Anthropic API costs** - set `OPENAI_MAX_CONCURRENT` appropriately

## Troubleshooting

### Check Container Health
```bash
# Test container locally
docker run --rm --env-file .env member-insights-processor:latest python src/main.py --validate
```

### View Cloud Run Logs
```bash
gcloud run services logs read ${SERVICE_NAME} --region ${REGION} --limit 100
```

### Debug Job Execution
```bash
# Get job execution details
gcloud run jobs executions describe EXECUTION_NAME \
  --job ${SERVICE_NAME}-job \
  --region ${REGION}
```

### Common Issues

1. **Secret access denied**: Verify service account has `secretAccessor` role
2. **BigQuery permissions**: Ensure service account has `bigquery.dataViewer` and `bigquery.jobUser`
3. **Timeout errors**: Increase timeout or reduce batch size
4. **Memory issues**: Increase memory allocation or reduce `--max-concurrent-contacts`

## Production Checklist

- [ ] Secrets stored in Secret Manager
- [ ] Service account with least-privilege permissions
- [ ] Cloud Logging enabled
- [ ] Cloud Monitoring alerts configured
- [ ] Resource limits set appropriately
- [ ] Cost monitoring dashboards created
- [ ] Backup and disaster recovery plan
- [ ] Documentation updated with deployment details
- [ ] Load testing completed
- [ ] Error handling and retry logic tested

## Next Steps

1. Set up Cloud Scheduler for automated runs
2. Configure Cloud Monitoring dashboards
3. Implement custom metrics for business insights
4. Set up Cloud Functions for event-driven processing
5. Create CI/CD pipeline for automated deployments
