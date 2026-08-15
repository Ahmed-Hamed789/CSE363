# Architecture

![Architecture diagram](architecture.png)

## Reading the diagram

- **Solid teal arrows** are synchronous HTTP/TCP calls that block until a response comes back.
- **Dashed amber arrows** are asynchronous — a message is dropped somewhere and the sender moves on without waiting.
- The **dashed black boundary** is the VPC (`10.0.0.0/16`), split into three subnet tiers across two Availability Zones. Only the public tier has a route to `0.0.0.0/0`; the DB tier has none.
- Everything to the right of the VPC boundary (the three S3 buckets, SQS, SNS) is a regional AWS service reached over the public AWS API endpoints via the app subnet's internet gateway route — not a VPC-internal resource, since no VPC endpoints are used in this project.

## Why the frontend bypasses the ALB

The browser loads `frontend/index.html` directly from the public `cse363-frontend` bucket — that's a plain static-website GET, no reason to route it through the compute tier. Only the page's own JavaScript, once running in the browser, calls the ALB for `/api/...` requests. That's why the diagram draws two separate arrows out of Browser: one straight to S3 for the page itself, one to the ALB for everything the page then does.

## Why nothing points from Quiz Service to `docs_db` or the documents bucket

Because nothing does. The Quiz Service's only inbound connection to the rest of the system is the SQS message, which already carries everything it needs (`document_id`, extracted `text`). See [`report.md`](../report.md) for the isolation argument this enforces.
