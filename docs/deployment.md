# Deployment

## Overview

MedLens is designed to be deployed as a Dockerized full-stack web application on AWS. The deployment architecture emphasizes reproducibility, scalability, and production-style engineering practices while remaining simple enough for a single-developer project.

The application will initially be deployed to a single AWS EC2 instance using Docker Compose, with optional future improvements such as managed databases, reverse proxies, and container orchestration.

---

## Deployment Architecture

The planned production environment consists of:

- React frontend
- FastAPI backend
- PostgreSQL database
- Docker containers
- AWS EC2
- AWS S3 (for uploaded files)

```text
                 Internet
                     │
                     ▼
              AWS EC2 Instance
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
    Frontend     FastAPI      PostgreSQL
    Container    Container     Container
                     │
                     ▼
                Gemini API

(Optional)

FastAPI ─────────────► AWS S3
```

---

## Local Development

Local development will use Docker Compose to ensure every service can be started consistently.

Planned containers:

- frontend
- backend
- postgres

The application should be runnable with:

```bash
docker compose up --build
```

---

## Production Environment

The initial production deployment will include:

- Dockerized frontend
- Dockerized backend
- PostgreSQL
- Environment variables
- Persistent database storage
- Structured application logs

Future versions may include:

- Nginx reverse proxy
- HTTPS
- Load balancing
- Managed PostgreSQL (AWS RDS)

---

## Environment Variables

Configuration values will be managed through environment variables.

Examples include:

- DATABASE_URL
- JWT_SECRET_KEY
- GEMINI_API_KEY
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY
- AWS_REGION
- S3_BUCKET_NAME

Sensitive values will never be committed to the repository.

An `.env.example` file will document required variables.

---

## Docker Strategy

Each major component will have its own Dockerfile.

Planned containers:

- frontend
- backend
- postgres

Docker Compose will coordinate communication between services for both local development and production deployment.

---

## Continuous Integration

GitHub Actions will automatically verify code quality for every pull request.

Planned checks include:

- Backend unit tests
- Frontend tests
- TypeScript checks
- Linting
- Docker image builds

---

## Continuous Deployment

The planned deployment workflow is:

1. Push changes to a feature branch.
2. Open a pull request.
3. Run automated tests.
4. Merge into `develop`.
5. Merge release into `main`.
6. Build Docker images.
7. Deploy the latest version to AWS EC2.

---

## Monitoring

The deployed application will include basic observability features such as:

- Health endpoint
- Request logging
- Error logging
- Processing time metrics
- Database connectivity checks

Future improvements may include:

- AWS CloudWatch
- Sentry
- Performance dashboards

---

## Future Improvements

Potential production improvements include:

- AWS RDS
- Redis
- Celery background workers
- Nginx reverse proxy
- HTTPS certificates
- Kubernetes
- Auto-scaling
- Blue-green deployments
- Custom domain

---

## Deployment Goals

The deployment strategy is intended to demonstrate production engineering practices, including:

- Containerized development
- Cloud deployment
- Infrastructure as code
- Automated testing
- Continuous integration
- Secure configuration management
- Scalable application architecture

---

## Status

This document outlines the intended deployment strategy and will evolve as deployment infrastructure is implemented throughout the project.