# AWS Infrastructure & Manual Setup Guide

This guide documents all AWS configurations, IAM policies, S3 buckets, and cloud resources that are created outside of GitHub and are required to run, test, and deploy the **AgenticAutomation** application.

---

## 1. General Configuration

* **AWS Region**: `ap-south-1` (Asia Pacific - Mumbai)
* **Application Port**: `5000`
* **Container Architecture**: Linux / `AMD64` (AWS Fargate)

---

## 2. Amazon ECR (Elastic Container Registry)

Stores the built application Docker images.

* **Repository Name**: `agenticautomation`
* **Visibility**: Private
* **Registry URI**: `<AWS_ACCOUNT_ID>.dkr.ecr.ap-south-1.amazonaws.com/agenticautomation`
* **Creation via CLI**:
  ```bash
  aws ecr create-repository --repository-name agenticautomation --region ap-south-1
  ```
* **Or via AWS Console**:
  1. Open Amazon ECR Console (Region: `ap-south-1`).
  2. Click **Create repository** → select **Private**.
  3. Name: `agenticautomation` → click **Create repository**.

---

## 3. Amazon S3 Buckets

The application requires two private S3 buckets in region **`ap-south-1`**:

| Bucket Name | Purpose | What Goes Inside |
| :--- | :--- | :--- |
| **`agenticautomation-input-test`** | **Input Landing Bucket** | Upload raw document files (`.txt`, `.pdf`, invoices, contracts) here for processing |
| **`agenticautomation-data-test`** | **State & Output Bucket** | Stores workflow run state (`workflows/index.json`), step history (`steps.json`), and extracted Bedrock JSON (`extracted.json`) |

### Bucket Creation Settings:
* **Region**: `ap-south-1` (Mumbai)
* **Block all public access**: **Enabled** (Keep private)
* **Encryption**: Server-side encryption with Amazon S3 managed keys (SSE-S3)
* **Creation via CLI**:
  ```bash
  aws s3 mb s3://agenticautomation-input-test --region ap-south-1
  aws s3 mb s3://agenticautomation-data-test --region ap-south-1
  ```

### Uploading Test Documents:
Upload sample files (e.g. from the repository's `./sample_files/` folder) into the input bucket:
```bash
aws s3 cp sample_files/contract_vendor_A.txt s3://agenticautomation-input-test/sample_files/contract_vendor_A.txt
aws s3 cp sample_files/invoice_Q3.txt s3://agenticautomation-input-test/sample_files/invoice_Q3.txt
```
*(The application automatically finds files located either at the bucket root or under a `sample_files/` folder).*

---

## 4. Amazon Bedrock Foundation Model Access

Before Bedrock can be invoked, models must be explicitly enabled in your AWS account for the region:

1. Open the [Amazon Bedrock Console](https://ap-south-1.console.aws.amazon.com/bedrock/home?region=ap-south-1) (Region: `ap-south-1` Mumbai).
2. In the left navigation sidebar, click **Model access** (near the bottom).
3. Click the orange **Modify model access** (or **Enable all models**) button.
4. Ensure access is granted for:
   * **Amazon**:
     * **Nova Lite** (Profile: `apac.amazon.nova-lite-v1:0` / Base: `amazon.nova-lite-v1:0`) — Used for contract analysis
     * **Nova Micro** (Profile: `apac.amazon.nova-micro-v1:0` / Base: `amazon.nova-micro-v1:0`) — Used for reports and fallback
     > **Note**: Amazon Bedrock requires invoking Nova models via cross-region inference profiles (`apac.amazon.nova-...`) when using on-demand throughput.
   * **Anthropic**:
     * **Claude 3 Haiku** (`anthropic.claude-3-haiku-20240307-v1:0`) — Used for invoice parsing
5. Click **Next** → click **Submit**. *(Amazon Nova model access is granted immediately).*

---

## 5. IAM Roles & Policies

Three separate IAM identities are required:

### A. CI/CD Deployment User 
The IAM user whose credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) are stored in GitHub Secrets.

* **Permissions Attached**:
  1. **`AmazonEC2ContainerRegistryPowerUser`** (AWS Managed Policy) — Allows authenticating with ECR and pushing container images.
  2. **`ECSDeployPolicy`** (Inline Policy) — Allows registering task definitions, updating ECS services, and passing roles:
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [
         {
           "Sid": "ECSDeploymentActions",
           "Effect": "Allow",
           "Action": [
             "ecs:RegisterTaskDefinition",
             "ecs:DescribeTaskDefinition",
             "ecs:DescribeServices",
             "ecs:UpdateService"
           ],
           "Resource": "*"
         },
         {
           "Sid": "PassRoleToECSTasks",
           "Effect": "Allow",
           "Action": "iam:PassRole",
           "Resource": [
             "arn:aws:iam::<AWS_ACCOUNT_ID>:role/agenticautomation-ecs-execution-role",
             "arn:aws:iam::<AWS_ACCOUNT_ID>:role/agenticautomation-ecs-task-role"
           ]
         }
       ]
     }
     ```

---

### B. Task Execution Role (`agenticautomation-ecs-execution-role`)
Used by the AWS ECS Agent (infrastructure level) to pull Docker images from ECR and stream logs to CloudWatch.

* **Role Name**: `agenticautomation-ecs-execution-role`
* **Trusted Entity (Trust Relationship)**:
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Service": "ecs-tasks.amazonaws.com"
        },
        "Action": "sts:AssumeRole"
      }
    ]
  }
  ```
* **Policies Attached**:
  1. **`AmazonECSTaskExecutionRolePolicy`** (AWS Managed Policy)
  2. **`AllowCreateLogGroup`** (Inline Policy) — Allows auto-creating the CloudWatch log group:
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Action": "logs:CreateLogGroup",
           "Resource": "*"
         }
       ]
     }
     ```

---

### C. Task Role (`agenticautomation-ecs-task-role`)
Assumed by the running Python/Flask container application to interact with S3 and invoke Amazon Bedrock models.

* **Role Name**: `agenticautomation-ecs-task-role`
* **Trusted Entity (Trust Relationship)**:
  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Principal": {
          "Service": "ecs-tasks.amazonaws.com"
        },
        "Action": "sts:AssumeRole"
      }
    ]
  }
  ```
* **Policies Attached**:
  1. **`AmazonS3FullAccess`** (AWS Managed Policy) — Allows reading documents from `agenticautomation-input-test` and writing workflow state/extracted JSON to `agenticautomation-data-test`.
  2. **`AmazonBedrockFullAccess`** (AWS Managed Policy) — Allows invoking Amazon Bedrock models (`InvokeModel` for Claude and Nova).
     *(Or attach a custom inline policy granting `bedrock:InvokeModel` and `bedrock:InvokeModelWithResponseStream` on `*`).*

---

## 6. Amazon CloudWatch Logs

Captures all Gunicorn, Flask, document processing, and Bedrock invocation logs.

* **Log Group Name**: `/ecs/agenticautomation`
* **Region**: `ap-south-1`
* **Auto-creation**: Handled automatically on first task launch via `"awslogs-create-group": "true"` in the task definition.
* **Manual Creation (if needed)**:
  ```bash
  aws logs create-log-group --log-group-name /ecs/agenticautomation --region ap-south-1
  ```

---

## 7. Amazon ECS Cluster & Service

### A. Cluster
* **Cluster Name**: `agenticautomation-cluster`
* **Infrastructure**: **AWS Fargate** (Serverless compute)
* **Creation**:
  1. In ECS Console → **Clusters** → **Create cluster**.
  2. Name: `agenticautomation-cluster` → Infrastructure: **AWS Fargate** → **Create**.

### B. Service
* **Service Name**: `agenticautomation-service` *(must match this exact name)*
* **Task Definition Family**: `agenticautomation`
* **Launch Type**: `FARGATE`
* **Desired Tasks**: `1` (or `0` when paused)
* **Networking**:
  * **VPC**: Default VPC
  * **Subnets**: Default public subnets
  * **Auto-assign Public IP**: **ENABLED** (required to pull from ECR and reach Bedrock)
* **Security Group Rules**:
  * **Type**: `Custom TCP`
  * **Port**: `5000`
  * **Source**: `0.0.0.0/0` (Anywhere IPv4) or your IP

---

## 8. GitHub Repository Secrets

Configure in GitHub: **Settings → Secrets and variables → Actions**:

| Secret Name | Description | Example / Note |
| :--- | :--- | :--- |
| `AWS_ACCESS_KEY_ID` | IAM Access Key for `iam-user` | `AKIAIO123123Example` |
| `AWS_SECRET_ACCESS_KEY` | IAM Secret Key for `iam-user` | `wJa123123` |
| `AWS_ACCOUNT_ID` | 12-digit AWS Account ID | `123456789012` |

---

## 9. End-to-End Testing & Verification

Once deployed to ECS Fargate:

### 1. Get the Task Public IP
1. In ECS Console → **Clusters** → `agenticautomation-cluster` → **Services** → `agenticautomation-service`.
2. Under the **Tasks** tab, click on the running **Task ID**.
3. Under **Networking**, copy the **Public IP** (e.g. `13.234.xxx.xxx`).

### 2. Verify Health Check
```bash
curl http://<PUBLIC_IP>:5000/health
# Response: {"service": "agenticautomation", "status": "healthy"}
```

### 3. Open Web Dashboard UI
Open in your browser:
```
http://<PUBLIC_IP>:5000/
```
The **AgenticAutomation Dashboard SPA** will display workflow history and execution status.

### 4. Trigger Document Processing (Bedrock Invocation)
Upload a document to S3 (or use an existing one in `agenticautomation-input-test`), then trigger:
```bash
curl -X POST http://<PUBLIC_IP>:5000/api/trigger \
  -H "Content-Type: application/json" \
  -d '{"filename": "contract_vendor_A.txt"}'
```
* Response returns `201 Created` with `workflow_id`, model ID (`amazon.nova-lite-v1:0`), and status `POSTED`.
* The extracted JSON is saved to `s3://agenticautomation-data-test/workflows/<workflow_id>/extracted.json`.

---

## 10. Cost Management (Pausing & Resuming)

* **To Stop All Compute Charges ($0 Cost Overnight)**:
  In ECS Console → `agenticautomation-cluster` → `agenticautomation-service`:
  1. Click **Update service**.
  2. Set **Desired tasks** to **`0`**.
  3. Click **Update**.
  *(Fargate container terminates immediately. Zero running tasks = $0 compute charges).*

* **To Resume**:
  1. In `agenticautomation-service`, click **Update service**.
  2. Set **Desired tasks** back to **`1`**.
  3. Click **Update** *(or push a new commit to `master` to trigger GitHub Actions)*.

* **After Updating IAM Roles**:
  Whenever policies on `agenticautomation-ecs-task-role` are updated, click **Update service** → check **Force new deployment** → click **Update** so the task restarts with fresh credentials.
