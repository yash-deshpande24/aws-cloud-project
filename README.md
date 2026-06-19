# ☁️ Cloud Hosting & Networking Project — AWS

A complete, production-ready AWS infrastructure project covering **EC2, S3, VPC, IAM, ELB, and CloudFormation**.

---

## 📁 Project Structure

```
aws-cloud-project/
├── cloudformation/
│   ├── main-stack.yaml       # Root stack (nested stacks)
│   ├── vpc-stack.yaml        # VPC, subnets, IGW, NAT, route tables, NACLs
│   ├── iam-stack.yaml        # IAM roles, policies, users, instance profiles
│   ├── s3-stack.yaml         # Assets, logs, and backups S3 buckets
│   └── compute-stack.yaml    # EC2 ASG + Application Load Balancer
├── ec2/
│   ├── bootstrap.sh          # EC2 instance initialization script
│   └── ec2_manager.py        # List, start, stop, describe instances
├── s3/
│   └── s3_manager.py         # Upload, download, sync, presign URLs
├── vpc/
│   └── vpc_inspector.py      # Inspect VPC, subnets, routes, audit SGs
├── iam/
│   └── iam_auditor.py        # List users/roles, security audit
├── elb/
│   └── elb_monitor.py        # ALB health, targets, CloudWatch metrics
├── scripts/
│   ├── deploy.sh             # Full stack deploy (create or update)
│   └── teardown.sh           # Safely delete all AWS resources
├── requirements.txt
└── README.md
```

---

## 🏗️ Architecture

```
Internet
   │
   ▼
┌──────────────────────────────────────┐
│         Application Load Balancer    │  ← ELB (public subnets, 2 AZs)
└──────────────┬───────────────────────┘
               │
┌──────────────▼───────────────────────┐
│  VPC  10.0.0.0/16                    │
│                                      │
│  ┌─────────────┐  ┌───────────────┐  │
│  │ Public Net  │  │  Public Net   │  │  10.0.1.0/24 / 10.0.2.0/24
│  │  (AZ-1)     │  │   (AZ-2)      │  │
│  └──────┬──────┘  └───────────────┘  │
│         │ NAT GW                      │
│  ┌──────▼──────┐  ┌───────────────┐  │
│  │ Private Net │  │  Private Net  │  │  10.0.3.0/24 / 10.0.4.0/24
│  │  EC2 ASG    │  │   EC2 ASG     │  │
│  └─────────────┘  └───────────────┘  │
└──────────────────────────────────────┘
               │
        ┌──────▼──────┐
        │  S3 Buckets  │  ← Assets, Logs, Backups
        └─────────────┘
```

---

## 🚀 Quick Start

### Prerequisites
- AWS CLI configured (`aws configure`)
- Python 3.8+ and pip
- An EC2 Key Pair in your target region
- An S3 bucket to store CloudFormation templates

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Set environment variables
```bash
export PROJECT_NAME="cloud-hosting-project"
export ENVIRONMENT="production"
export AWS_REGION="us-east-1"
export KEY_PAIR_NAME="your-key-pair-name"
export S3_DEPLOY_BUCKET="your-cfn-templates-bucket"
export SSH_CIDR="YOUR_IP/32"          # Restrict SSH to your IP
export INSTANCE_TYPE="t3.micro"
```

### 3. Deploy the full stack
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

The script will:
1. Upload CloudFormation templates to S3
2. Create or update the nested CloudFormation stacks
3. Output the ALB DNS name and other resource identifiers

---

## 🛠️ Service Tools

### EC2 Manager
```bash
# List all instances for project
python3 ec2/ec2_manager.py --region us-east-1 --project cloud-hosting-project list

# Describe a specific instance
python3 ec2/ec2_manager.py describe i-0abc123def456789

# Start / Stop
python3 ec2/ec2_manager.py start i-0abc123def456789
python3 ec2/ec2_manager.py stop  i-0abc123def456789
```

### S3 Manager
```bash
# Upload a file
python3 s3/s3_manager.py --bucket my-bucket upload ./index.html --key app/index.html

# Sync a directory
python3 s3/s3_manager.py --bucket my-bucket sync ./dist --prefix app/

# Generate a pre-signed URL (valid 1 hour)
python3 s3/s3_manager.py --bucket my-bucket presign app/index.html --expiry 3600

# Show bucket size
python3 s3/s3_manager.py --bucket my-bucket size
```

### VPC Inspector
```bash
# Full VPC info
python3 vpc/vpc_inspector.py --vpc-id vpc-0abc12345 --region us-east-1

# Security audit (flags open SSH, all-traffic rules)
python3 vpc/vpc_inspector.py --vpc-id vpc-0abc12345 --audit
```

### IAM Auditor
```bash
# List users with MFA/key status
python3 iam/iam_auditor.py list-users

# Detect security issues
python3 iam/iam_auditor.py audit

# Generate least-privilege S3 policy
python3 iam/iam_auditor.py gen-policy --role my-role --bucket my-bucket
```

### ELB Monitor
```bash
# List load balancers
python3 elb/elb_monitor.py --region us-east-1 list

# Health report with CloudWatch metrics
python3 elb/elb_monitor.py --region us-east-1 --project cloud-hosting-project health

# Target group targets
python3 elb/elb_monitor.py targets arn:aws:elasticloadbalancing:...
```

---

## 🔒 Security Best Practices Applied

| Area | Practice |
|------|----------|
| VPC | Public/private subnet separation; NAT Gateway for outbound-only private traffic |
| EC2 | Instances in private subnets; ELB in public subnets only |
| IAM | Least-privilege policies; EC2 instance role (no static keys); MFA enforcement |
| S3 | Bucket encryption (AES256 / KMS); versioning; lifecycle rules; HTTPS-only policy |
| ELB | Security group restricts EC2 to ALB traffic only |
| Secrets | No secrets hardcoded; deploy user keys via CloudFormation outputs |

---

## 🗑️ Teardown

```bash
export PROJECT_NAME="cloud-hosting-project"
export AWS_REGION="us-east-1"
chmod +x scripts/teardown.sh
./scripts/teardown.sh
```

> **Warning:** This permanently deletes all resources and S3 data.

---

## 📄 CloudFormation Stacks

| Stack | Template | Purpose |
|-------|----------|---------|
| Root | `main-stack.yaml` | Orchestrates nested stacks, passes parameters |
| VPC | `vpc-stack.yaml` | Network layer: VPC, subnets, IGW, NAT, routes, NACLs |
| IAM | `iam-stack.yaml` | EC2 role, deploy user, read-only role |
| S3 | `s3-stack.yaml` | Assets, logs, and backups buckets with policies |
| Compute | `compute-stack.yaml` | ALB, target group, ASG, launch template, security groups |
