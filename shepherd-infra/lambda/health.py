import json
import os

def handler(event, context):
    print("Health check invoked")
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "OPTIONS,GET"
        },
        "body": json.dumps({
            "status": "healthy",
            "project": "SHEPHERD",
            "environment": os.environ.get("ENVIRONMENT", "hackathon"),
            "venueMetricsTable": os.environ.get("VENUE_METRICS_TABLE", ""),
            "incidentsTable": os.environ.get("INCIDENTS_TABLE", ""),
            "operationalTasksTable": os.environ.get("OPERATIONAL_TASKS_TABLE", ""),
            "evidenceBucket": os.environ.get("EVIDENCE_BUCKET_NAME", "")
        })
    }
