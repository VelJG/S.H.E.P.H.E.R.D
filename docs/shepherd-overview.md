# S.H.E.P.H.E.R.D. Overview

**S.H.E.P.H.E.R.D. — Smart Human-flow Evaluation, Prediction, Hazard Detection, Response, and Dispatch** turns live camera footage into real-time crowd intelligence using computer vision and an AI operations agent. It helps venue operators evaluate crowd flow, detect signs of congestion, predict possible overcrowding, and dispatch staff with clear, actionable recommendations.

## Inspiration

S.H.E.P.H.E.R.D. was inspired by the operational challenges of managing busy physical venues, where staff must monitor entrances, queues, booths, and crowd movement across multiple areas at once. Manual monitoring can be slow, reactive, and difficult to scale, especially when crowd conditions change quickly. We wanted to build a system that helps operators detect issues earlier and respond before congestion becomes a problem.

## What It Does

S.H.E.P.H.E.R.D. analyzes live camera footage to detect and track people, measure crowd density, estimate queue conditions, and identify early signs of congestion. On top of the vision pipeline, an AI operations agent continuously monitors live metrics, creates proactive alerts, predicts possible overcrowding, and recommends staff actions.

Operators can also ask the agent natural-language questions like:

- “Which area is getting crowded?”
- “Where should we send staff?”
- “Summarize the last 10 minutes.”
- “Is any booth showing signs of congestion?”

## How We Built It

We use a phone camera as the live video source. Frames are processed with OpenCV and ByteTrack for tracking, while YOLO is hosted on an Amazon SageMaker real-time endpoint for person detection. The resulting crowd and queue metrics are sent to the backend and displayed in a React dashboard hosted on Amazon S3 and CloudFront.

The AI agent layer reads those live metrics, invokes operational tools such as congestion prediction and shift reporting, and uses an LLM to generate clear dispatcher-ready recommendations. For the demo, the agent can run locally for reliability, while the AWS architecture includes API Gateway, Lambda, DynamoDB, and Bedrock-ready routes for the cloud version.

## Agentic AI Layer

S.H.E.P.H.E.R.D. includes both:

1. **Autonomous Monitor Agent**  
   Continuously watches live crowd metrics, detects signs of congestion, predicts overcrowding pressure, and creates proactive alerts.

2. **Operator Copilot Agent**  
   Lets staff ask natural-language questions and receive concise answers backed by live metrics, prediction tools, and recommended actions.

The agent does not just return static data. It chooses tools, reads current venue state, evaluates crowd flow, predicts issues, and recommends dispatch actions.

## What We Learned

We learned how to combine real-time computer vision, object tracking, cloud inference, operational dashboards, and agentic AI into one workflow. We also learned that reliable streaming, low-latency inference, camera placement, and clear operator-facing alerts are just as important as model accuracy.

## Challenges

The main challenges were maintaining reliable live video, reducing inference latency, preserving tracking between frames, and keeping the full system small enough to complete within the hackathon timeline. Another challenge was making the AI agent useful in real operations: it needed to be proactive, explainable, and actionable rather than just a chatbot.
