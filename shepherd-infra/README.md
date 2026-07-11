# S.H.E.P.H.E.R.D. Infrastructure

This package contains the AWS CDK infrastructure for **S.H.E.P.H.E.R.D.**:

**Smart Human-flow Evaluation, Prediction, Hazard Detection, Event Response, and Dispatch**

S.H.E.P.H.E.R.D. is an AI-powered real-time venue operations monitoring system that turns live camera footage into operational insight for venue staff.

## Project Overview

A phone camera is placed at a strategic area such as an entrance, registration counter, corridor, or queue. The system detects and tracks people, measures crowd and queue conditions, and alerts operators when congestion occurs.

### Problem

Venue operators often rely on staff manually watching CCTV feeds or physically checking busy areas. This can lead to:

- delayed congestion detection;
- slow staff response;
- inaccurate queue estimates;
- poor visibility across the venue;
- underuse of existing camera systems.

### Proposed Solution

The system will:

- receive a live stream from a phone camera;
- detect people using YOLO hosted on Amazon SageMaker;
- track people using ByteTrack;
- measure occupancy and queue length;
- detect congestion using configurable thresholds;
- create incidents and response tasks;
- display the results on a web dashboard;
- store incident screenshots and backup recordings.

## Main Workflow

```text
Phone Camera
    ↓
Laptop Stream Processor
    ↓
Amazon SageMaker YOLO Detection
    ↓
ByteTrack and Zone Analysis
    ↓
AWS Backend
    ↓
Dashboard, Incidents, and Tasks
```

## Core Features

- live phone-camera monitoring;
- person detection;
- person tracking;
- occupancy counting;
- queue estimation;
- congestion alerts;
- incident management;
- operational task tracking;
- recorded-video backup;
- AWS-hosted dashboard.

## AWS Services

Project services in scope:

- Amazon SageMaker AI;
- Amazon ECR;
- Amazon API Gateway;
- AWS Lambda;
- Amazon DynamoDB;
- Amazon S3;
- Amazon CloudFront;
- Amazon CloudWatch;
- AWS IAM.

## Technology Stack

- Python;
- OpenCV;
- YOLO;
- ByteTrack;
- React;
- TypeScript;
- Vite;
- Docker.

## Infrastructure in This CDK Package

The current CDK stack provisions the core AWS foundation for the prototype, including:

- a private S3 bucket for the frontend;
- a CloudFront distribution for frontend delivery;
- an S3 bucket for evidence and stored artifacts;
- an ECR repository for container images;
- a SageMaker execution role;
- an API Gateway HTTP API;
- a Lambda backend integration;
- DynamoDB tables for:
  - venue metrics;
  - incidents;
  - operational tasks.

## Hackathon Scope

The prototype supports:

- one phone camera;
- one live video stream;
- one or two monitoring zones;
- near-real-time person detection;
- crowd and queue monitoring;
- one congestion alert workflow;
- one basic response-task workflow;
- live and recorded demo modes.

## Out of Scope

- multiple cameras;
- face recognition;
- cross-camera tracking;
- mobile staff application;
- advanced authentication;
- full CCTV playback;
- long-term analytics;
- multiple venue branches.

## Project Value

S.H.E.P.H.E.R.D. helps venue operators notice operational problems earlier and respond faster.

The same concept can later be applied to:

- event venues;
- supermarkets;
- airports;
- campuses;
- hospitals;
- transportation hubs;
- other high-traffic environments.

## Elevator Pitch

S.H.E.P.H.E.R.D. transforms live camera footage into real-time operational intelligence. Using Amazon SageMaker-powered computer vision, it detects and tracks people, measures queue and crowd conditions, and alerts venue operators when congestion occurs. The system helps staff understand incidents and coordinate faster responses through a simple AWS-hosted dashboard.

## Useful Commands

- `npm run build` — compile TypeScript to JavaScript
- `npm run watch` — watch for changes and compile
- `npm run test` — run unit tests
- `npx cdk synth` — synthesize the CloudFormation template
- `npx cdk diff` — compare deployed stack with current state
- `npx cdk deploy` — deploy the stack to your default AWS account/region
