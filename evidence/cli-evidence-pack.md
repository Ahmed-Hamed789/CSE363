# CSE363 Milestone 1 — CLI Evidence Pack

Every item from the spec's §17 screenshot checklist, captured as verifiable AWS CLI command output instead of console screenshots. All commands run against account `339879234587`, region `us-east-1`, timestamped 2026-08-03.

---

## VPC — 1.5 marks

### 1. VPC details showing `10.0.0.0/16`
```
$ aws ec2 describe-vpcs --vpc-ids vpc-0b0fab97d23abaa11
```
```json
{
  "VpcId": "vpc-0b0fab97d23abaa11",
  "CidrBlock": "10.0.0.0/16",
  "State": "available",
  "IsDefault": false,
  "Tags": [{ "Key": "Name", "Value": "cse363-vpc" }]
}
```

### 2. Six subnets
```
$ aws ec2 describe-subnets --filters Name=vpc-id,Values=vpc-0b0fab97d23abaa11
```
| Name | Subnet ID | AZ | CIDR | Auto-assign public IP |
|---|---|---|---|---|
| cse363-public-a | subnet-0929527ba16945eb9 | us-east-1a | 10.0.1.0/24 | True |
| cse363-public-b | subnet-0d06a1a2940301deb | us-east-1b | 10.0.2.0/24 | True |
| cse363-app-a | subnet-0e39e4de41a26b7fe | us-east-1a | 10.0.11.0/24 | True |
| cse363-app-b | subnet-06061329f8b5657cc | us-east-1b | 10.0.12.0/24 | True |
| cse363-db-a | subnet-0100130dbdd4f4aad | us-east-1a | 10.0.21.0/24 | False |
| cse363-db-b | subnet-040028ae7287ad8f2 | us-east-1b | 10.0.22.0/24 | False |

### 3. Internet Gateway attached
```
$ aws ec2 describe-internet-gateways --filters Name=attachment.vpc-id,Values=vpc-0b0fab97d23abaa11
```
```json
{
  "InternetGatewayId": "igw-0ae998687750df66f",
  "Tags": [{ "Key": "Name", "Value": "cse363-igw" }],
  "Attachments": [{ "State": "available", "VpcId": "vpc-0b0fab97d23abaa11" }]
}
```

### 4. Public/app route tables with `0.0.0.0/0 → IGW`
`cse363-public-rt` (rtb-0a61ebb70b416f9f2, associated: public-a, public-b):
```json
[
  { "DestinationCidrBlock": "10.0.0.0/16", "GatewayId": "local" },
  { "DestinationCidrBlock": "0.0.0.0/0", "GatewayId": "igw-0ae998687750df66f" }
]
```
`cse363-app-rt` (rtb-08164ab6d834c78f9, associated: app-a, app-b):
```json
[
  { "DestinationCidrBlock": "10.0.0.0/16", "GatewayId": "local" },
  { "DestinationCidrBlock": "0.0.0.0/0", "GatewayId": "igw-0ae998687750df66f" }
]
```

### 5. Database route table with local route only
`cse363-db-rt` (rtb-0df536fc8520bb005, associated: db-a, db-b):
```json
[
  { "DestinationCidrBlock": "10.0.0.0/16", "GatewayId": "local" }
]
```
No `0.0.0.0/0` route present. No NAT Gateway exists in the account.

### 6. Subnet allocation table
See item 2 above — matches the spec's table exactly.

---

## Security groups and ALB — 1.5 marks

### 1. `CSE363-App-SG` inbound — port 80 from `CSE363-ALB-SG`
```
$ aws ec2 describe-security-groups --group-ids sg-0edb9fc8b6f3d6e0f
```
```json
"IpPermissions": [
  { "IpProtocol": "tcp", "FromPort": 80, "ToPort": 80,
    "UserIdGroupPairs": [{ "GroupId": "sg-09ebc8cafee47b775" }] },
  { "IpProtocol": "tcp", "FromPort": 22, "ToPort": 22,
    "IpRanges": [{ "CidrIp": "154.180.239.247/32" }] }
]
```
`sg-09ebc8cafee47b775` = `CSE363-ALB-SG`. Port 80 source is the ALB security group, not an IP range. SSH restricted to a single operator IP, not `0.0.0.0/0`.

### 2. `CSE363-DB-SG` — port 5432 from `CSE363-App-SG`
```
$ aws ec2 describe-security-groups --group-ids sg-081ca0ee05109a659
```
```json
"IpPermissions": [
  { "IpProtocol": "tcp", "FromPort": 5432, "ToPort": 5432,
    "UserIdGroupPairs": [{ "GroupId": "sg-0edb9fc8b6f3d6e0f" }] }
]
```
`sg-0edb9fc8b6f3d6e0f` = `CSE363-App-SG`. Confirms the full chain: `CSE363-ALB-SG → CSE363-App-SG → CSE363-DB-SG`.

### 3. ALB details showing two public subnets
```
$ aws elbv2 describe-load-balancers --names cse363-alb
```
```json
{
  "LoadBalancerName": "cse363-alb",
  "DNSName": "cse363-alb-614549833.us-east-1.elb.amazonaws.com",
  "Scheme": "internet-facing",
  "State": { "Code": "active" },
  "Type": "application",
  "AvailabilityZones": [
    { "ZoneName": "us-east-1a", "SubnetId": "subnet-0929527ba16945eb9" },
    { "ZoneName": "us-east-1b", "SubnetId": "subnet-0d06a1a2940301deb" }
  ],
  "SecurityGroups": ["sg-09ebc8cafee47b775"]
}
```
Both subnets are `cse363-public-a` and `cse363-public-b`.

### 4. Target group showing Healthy
```
$ aws elbv2 describe-target-health --target-group-arn arn:...targetgroup/cse363-nginx-tg/95b362ce317617c5
```
```json
{
  "Target": { "Id": "i-00563b8d3747b28fc", "Port": 80 },
  "TargetHealth": { "State": "healthy" }
}
```

### 5. Placeholder page loaded through the ALB DNS
```
$ curl http://cse363-alb-614549833.us-east-1.elb.amazonaws.com/
```
Returns the full "CSE363 Cloud Learning Platform / Infrastructure Layer Online" placeholder HTML (200 OK).
```
$ curl -i http://cse363-alb-614549833.us-east-1.elb.amazonaws.com/health
HTTP/1.1 200 OK
...
OK
```

---

## S3 — 1 mark

### 1. All three buckets
```
$ aws s3api list-buckets
```
`cse363-documents`, `cse363-frontend`, `cse363-quizzes` — all present in account 339879234587.

### 2 & 3. Documents / Quizzes versioning
```
$ aws s3api get-bucket-versioning --bucket cse363-documents  →  {"Status": "Enabled"}
$ aws s3api get-bucket-versioning --bucket cse363-quizzes    →  {"Status": "Enabled"}
```

### 4 & 5. Documents / Quizzes Block Public Access on
```
$ aws s3api get-public-access-block --bucket cse363-documents
$ aws s3api get-public-access-block --bucket cse363-quizzes
```
Both return:
```json
{
  "BlockPublicAcls": true,
  "IgnorePublicAcls": true,
  "BlockPublicPolicy": true,
  "RestrictPublicBuckets": true
}
```

### 6. Frontend public configuration
```
$ aws s3api get-public-access-block --bucket cse363-frontend
```
```json
{ "BlockPublicAcls": false, "IgnorePublicAcls": false, "BlockPublicPolicy": false, "RestrictPublicBuckets": false }
```
```
$ aws s3api get-bucket-policy --bucket cse363-frontend
```
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "PublicReadFrontend",
    "Effect": "Allow",
    "Principal": "*",
    "Action": "s3:GetObject",
    "Resource": "arn:aws:s3:::cse363-frontend/*"
  }]
}
```
Public Access Block fully disabled and a bucket policy grants anonymous `GetObject` only — read-only public access, correctly scoped to this one bucket.

---

## IAM — 1 mark

### 1. `CSE363-EC2-Role`
```
$ aws iam get-role --role-name CSE363-EC2-Role
```
```json
{
  "RoleName": "CSE363-EC2-Role",
  "Arn": "arn:aws:iam::339879234587:role/CSE363-EC2-Role",
  "AssumeRolePolicyDocument": {
    "Statement": [{ "Effect": "Allow", "Principal": { "Service": "ec2.amazonaws.com" }, "Action": "sts:AssumeRole" }]
  }
}
```
Trust policy scoped to `ec2.amazonaws.com` only.

### 2 & 3. `DocumentServiceS3Policy` / `QuizServiceS3Policy`
```
$ aws iam get-role-policy --role-name CSE363-EC2-Role --policy-name DocumentServiceS3Policy
$ aws iam get-role-policy --role-name CSE363-EC2-Role --policy-name QuizServiceS3Policy
```
Both returned exactly as authored — scoped respectively to `cse363-documents`/`cse363-documents/*` and `cse363-quizzes`/`cse363-quizzes/*` only. (Also attached: AWS-managed `AmazonSSMManagedInstanceCore`, used to run remote commands on the instance during this build instead of opening broader SSH access.)

### 4. Policy JSON files in repository
`iam-policies/document-service-s3-policy.json`, `iam-policies/quiz-service-s3-policy.json` — committed in this repo, content matches the live IAM policies above exactly.

### 5. `aws sts get-caller-identity` output
Captured **from inside the EC2 instance itself** (stronger evidence than running it locally, since it proves the instance profile actually works):
```json
{
  "UserId": "AROAU6ITBRQNUMEZ5HHCG:i-00563b8d3747b28fc",
  "Account": "339879234587",
  "Arn": "arn:aws:sts::339879234587:assumed-role/CSE363-EC2-Role/i-00563b8d3747b28fc"
}
```
Full detail in [ec2-nginx-and-role-verification.txt](ec2-nginx-and-role-verification.txt).

---

## RDS — 1 mark

```
$ aws rds describe-db-instances --db-instance-identifier cse363-postgres
```

| Item | Value |
|---|---|
| 1. Status | `available` |
| 2. Engine | `postgres` |
| 3. Instance class | `db.t3.micro` |
| 4. Publicly accessible | `false` |
| 5. DB subnet group | `cse363-db-subnet-group` → `subnet-0100130dbdd4f4aad` (db-a) + `subnet-040028ae7287ad8f2` (db-b) |
| 6. Security group | `sg-081ca0ee05109a659` (`CSE363-DB-SG`), status `active` |
| MultiAZ | `false` (Single-AZ, as required) |
| EngineVersion | `18.3` |
| StorageType / AllocatedStorage | `gp3` / `20` GiB |
| BackupRetentionPeriod | `1` |
| DeletionProtection / PerformanceInsightsEnabled | `false` / `false` |

### 7. `\l` equivalent — the two databases
```json
[
  { "Name": "docs_db", "Owner": "cse363admin" },
  { "Name": "quiz_db", "Owner": "cse363admin" }
]
```

### 8. `\du` equivalent — the two users
```json
[
  { "Role name": "docs_user", "Can login": "t" },
  { "Role name": "quiz_user", "Can login": "t" }
]
```

### 9. `quiz_user` denied access to `docs_db`
```
$ PGPASSWORD=*** psql -h cse363-postgres.c8v6yk04a7xf.us-east-1.rds.amazonaws.com -U quiz_user -d docs_db
FATAL:  permission denied for database "docs_db"
DETAIL:  User does not have CONNECT privilege.
```
Full detail, including the successful counter-example (`docs_user → docs_db` succeeds), in [rds-database-isolation-proof.txt](rds-database-isolation-proof.txt).

---

## Budget — already completed by team, not re-verified here (no billing permissions granted to the build user by design).
