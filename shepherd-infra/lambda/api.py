import base64
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import unquote_plus

import boto3
from boto3.dynamodb.conditions import Key


dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')

VENUE_METRICS_TABLE = dynamodb.Table(os.environ['VENUE_METRICS_TABLE'])
INCIDENTS_TABLE = dynamodb.Table(os.environ['INCIDENTS_TABLE'])
OPERATIONAL_TASKS_TABLE = dynamodb.Table(os.environ['OPERATIONAL_TASKS_TABLE'])
CONFIG_ZONES_TABLE = dynamodb.Table(os.environ['CONFIG_ZONES_TABLE'])
EVIDENCE_BUCKET_NAME = os.environ['EVIDENCE_BUCKET_NAME']


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    route_key = event.get('routeKey', '')
    method = event.get('requestContext', {}).get('http', {}).get('method', '')
    raw_path = event.get('rawPath', '')
    print(json.dumps({'routeKey': route_key, 'method': method, 'rawPath': raw_path}))

    try:
        if route_key == 'GET /config/zones':
            return get_config_zones()
        if route_key == 'PUT /config/zones':
            return put_config_zones(event)
        if route_key == 'POST /metrics':
            return post_metrics(event)
        if route_key == 'GET /metrics/latest':
            return get_metrics_latest(event)
        if route_key == 'GET /uploads/presign':
            return get_upload_presign(event)
        if route_key == 'POST /incidents':
            return post_incident(event)
        if route_key == 'GET /incidents':
            return list_incidents(event)
        if route_key == 'GET /incidents/{id}':
            return get_incident(event)
        if route_key == 'PATCH /incidents/{id}':
            return patch_incident(event)
        if route_key == 'GET /tasks':
            return list_tasks(event)
        if route_key == 'GET /tasks/{id}':
            return get_task(event)
        if route_key == 'PATCH /tasks/{id}':
            return patch_task(event)
        return response(404, {'message': f'Route not found: {route_key or f"{method} {raw_path}"}'})
    except ValueError as exc:
        return response(400, {'message': str(exc)})
    except Exception as exc:
        print(f'Unhandled error: {exc}')
        return response(500, {'message': 'Internal server error', 'detail': str(exc)})


def response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
            'Access-Control-Allow-Methods': 'OPTIONS,GET,POST,PUT,PATCH',
        },
        'body': json.dumps(body, default=json_default),
    }


def json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    raise TypeError(f'Object of type {type(value)} is not JSON serializable')


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def decode_body(event: dict[str, Any]) -> Any:
    body = event.get('body')
    if body in (None, ''):
        return {}

    if event.get('isBase64Encoded'):
        body = base64.b64decode(body).decode('utf-8')

    parsed = json.loads(body)
    if isinstance(parsed, (dict, list)):
        return parsed
    raise ValueError('Request body must be a JSON object or array')


def require_path_param(event: dict[str, Any], name: str) -> str:
    value = (event.get('pathParameters') or {}).get(name)
    if not value:
        raise ValueError(f'Missing path parameter: {name}')
    return value


def query_params(event: dict[str, Any]) -> dict[str, str]:
    return event.get('queryStringParameters') or {}


def scan_all(table: Any, **kwargs: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    result = table.scan(**kwargs)
    items.extend(result.get('Items', []))
    while 'LastEvaluatedKey' in result:
        result = table.scan(ExclusiveStartKey=result['LastEvaluatedKey'], **kwargs)
        items.extend(result.get('Items', []))
    return items


def to_dynamo_value(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: to_dynamo_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_dynamo_value(item) for item in value]
    return value


def sorted_desc(items: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: str(item.get(field, '')), reverse=True)


def get_config_zones() -> dict[str, Any]:
    item = CONFIG_ZONES_TABLE.get_item(Key={'configId': 'default'}).get('Item', {})
    return response(200, {
        'configId': 'default',
        'zones': item.get('zones', []),
        'updatedAt': item.get('updatedAt'),
        'updatedBy': item.get('updatedBy'),
    })


def put_config_zones(event: dict[str, Any]) -> dict[str, Any]:
    payload = decode_body(event)
    if isinstance(payload, list):
        zones = payload
        metadata: dict[str, Any] = {}
    elif isinstance(payload, dict):
        zones = payload.get('zones')
        metadata = payload
    else:
        raise ValueError('Config payload must be a JSON object or array')

    if not isinstance(zones, list):
        raise ValueError('`zones` must be an array')

    item = {
        'configId': 'default',
        'zones': to_dynamo_value(zones),
        'updatedAt': metadata.get('updatedAt', now_iso()),
        'updatedBy': metadata.get('updatedBy', 'dashboard'),
    }
    CONFIG_ZONES_TABLE.put_item(Item=item)
    return response(200, {'message': 'Zones updated', 'item': item})


def post_metrics(event: dict[str, Any]) -> dict[str, Any]:
    payload = decode_body(event)
    request_timestamp = now_iso()

    if isinstance(payload, list):
        metrics = payload
    elif isinstance(payload, dict) and isinstance(payload.get('metrics'), list):
        metrics = payload['metrics']
    elif isinstance(payload, dict):
        metrics = [payload]
    else:
        raise ValueError('Metrics payload must be an object, array, or `{ metrics: [...] }`')

    written = 0
    for metric in metrics:
        if not isinstance(metric, dict):
            raise ValueError('Each metric item must be an object')
        zone_id = metric.get('zoneId')
        if not zone_id:
            raise ValueError('Each metric item must include `zoneId`')

        item = {
            'zoneId': str(zone_id),
            'timestamp': str(metric.get('timestamp', request_timestamp)),
            'source': metric.get('source', 'processor'),
            'status': metric.get('status', 'ok'),
            'occupancy': metric.get('occupancy', 0),
            'queueLength': metric.get('queueLength', 0),
            'congestionScore': metric.get('congestionScore', 0),
            'alert': metric.get('alert', False),
            'frameId': metric.get('frameId'),
            'polygonVersion': metric.get('polygonVersion'),
            'raw': metric.get('raw', {}),
        }
        item.update({k: v for k, v in metric.items() if k not in item})
        VENUE_METRICS_TABLE.put_item(Item=to_dynamo_value(item))
        written += 1

    return response(202, {'message': 'Metrics accepted', 'count': written})


def get_metrics_latest(event: dict[str, Any]) -> dict[str, Any]:
    params = query_params(event)
    zone_id = params.get('zoneId')

    if zone_id:
        result = VENUE_METRICS_TABLE.query(
            KeyConditionExpression=Key('zoneId').eq(zone_id),
            ScanIndexForward=False,
            Limit=1,
        )
        items = result.get('Items', [])
        return response(200, {'items': items, 'count': len(items)})

    items = scan_all(VENUE_METRICS_TABLE)
    latest_by_zone: dict[str, dict[str, Any]] = {}
    for item in items:
        item_zone = str(item.get('zoneId', ''))
        current = latest_by_zone.get(item_zone)
        if current is None or str(item.get('timestamp', '')) > str(current.get('timestamp', '')):
            latest_by_zone[item_zone] = item

    latest_items = sorted(latest_by_zone.values(), key=lambda item: str(item.get('zoneId', '')))
    return response(200, {'items': latest_items, 'count': len(latest_items)})


def get_upload_presign(event: dict[str, Any]) -> dict[str, Any]:
    params = query_params(event)
    file_name = unquote_plus(params.get('filename', 'snapshot.jpg'))
    content_type = params.get('contentType', 'image/jpeg')
    folder = params.get('folder', 'incidents')
    object_key = f'{folder}/{uuid.uuid4()}-{file_name}'
    expires_in = int(params.get('expiresIn', '900'))

    upload_url = s3_client.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': EVIDENCE_BUCKET_NAME,
            'Key': object_key,
            'ContentType': content_type,
        },
        ExpiresIn=expires_in,
    )

    return response(200, {
        'bucket': EVIDENCE_BUCKET_NAME,
        'key': object_key,
        'contentType': content_type,
        'expiresIn': expires_in,
        'uploadUrl': upload_url,
    })


def post_incident(event: dict[str, Any]) -> dict[str, Any]:
    payload = decode_body(event)
    if not isinstance(payload, dict):
        raise ValueError('Incident payload must be an object')

    created_at = payload.get('createdAt', now_iso())
    incident_id = payload.get('incidentId', str(uuid.uuid4()))
    incident_item = {
        'incidentId': incident_id,
        'status': payload.get('status', 'open'),
        'createdAt': created_at,
        'updatedAt': created_at,
        'zoneId': payload.get('zoneId', 'unknown'),
        'title': payload.get('title', 'Congestion detected'),
        'severity': payload.get('severity', 'medium'),
        'summary': payload.get('summary', 'Operational incident created by processor'),
        'evidenceKey': payload.get('evidenceKey'),
        'metrics': payload.get('metrics', {}),
        'source': payload.get('source', 'processor'),
    }
    incident_item.update({k: v for k, v in payload.items() if k not in incident_item})
    INCIDENTS_TABLE.put_item(Item=to_dynamo_value(incident_item))

    task_payload = payload.get('task', {}) if isinstance(payload.get('task', {}), dict) else {}
    task_id = task_payload.get('taskId', str(uuid.uuid4()))
    task_item = {
        'taskId': task_id,
        'incidentId': incident_id,
        'status': task_payload.get('status', 'open'),
        'updatedAt': created_at,
        'createdAt': created_at,
        'title': task_payload.get('title', f'Respond to incident {incident_id}'),
        'assignee': task_payload.get('assignee', 'unassigned'),
        'notes': task_payload.get('notes', payload.get('summary', '')),
        'priority': task_payload.get('priority', payload.get('severity', 'medium')),
    }
    OPERATIONAL_TASKS_TABLE.put_item(Item=to_dynamo_value(task_item))

    return response(201, {
        'message': 'Incident created',
        'incident': incident_item,
        'task': task_item,
    })


def list_incidents(event: dict[str, Any]) -> dict[str, Any]:
    params = query_params(event)
    status = params.get('status')
    limit = int(params.get('limit', '50'))

    if status:
        result = INCIDENTS_TABLE.query(
            IndexName='status-createdAt-index',
            KeyConditionExpression=Key('status').eq(status),
            ScanIndexForward=False,
            Limit=limit,
        )
        items = result.get('Items', [])
    else:
        items = sorted_desc(scan_all(INCIDENTS_TABLE), 'createdAt')[:limit]

    return response(200, {'items': items, 'count': len(items)})


def get_incident(event: dict[str, Any]) -> dict[str, Any]:
    incident_id = require_path_param(event, 'id')
    item = INCIDENTS_TABLE.get_item(Key={'incidentId': incident_id}).get('Item')
    if not item:
        return response(404, {'message': 'Incident not found'})
    return response(200, {'item': item})


def patch_incident(event: dict[str, Any]) -> dict[str, Any]:
    incident_id = require_path_param(event, 'id')
    existing = INCIDENTS_TABLE.get_item(Key={'incidentId': incident_id}).get('Item')
    if not existing:
        return response(404, {'message': 'Incident not found'})

    payload = decode_body(event)
    if not isinstance(payload, dict):
        raise ValueError('Incident patch payload must be an object')

    updated = dict(existing)
    updated.update(payload)
    updated['incidentId'] = incident_id
    updated['updatedAt'] = now_iso()

    if updated.get('status') == 'resolved' and not updated.get('resolvedAt'):
        updated['resolvedAt'] = updated['updatedAt']

    INCIDENTS_TABLE.put_item(Item=to_dynamo_value(updated))
    return response(200, {'message': 'Incident updated', 'item': updated})


def list_tasks(event: dict[str, Any]) -> dict[str, Any]:
    params = query_params(event)
    status = params.get('status')
    incident_id = params.get('incidentId')
    limit = int(params.get('limit', '50'))

    if status:
      result = OPERATIONAL_TASKS_TABLE.query(
          IndexName='status-updatedAt-index',
          KeyConditionExpression=Key('status').eq(status),
          ScanIndexForward=False,
          Limit=limit,
      )
      items = result.get('Items', [])
    else:
      items = sorted_desc(scan_all(OPERATIONAL_TASKS_TABLE), 'updatedAt')

    if incident_id:
        items = [item for item in items if str(item.get('incidentId', '')) == incident_id]

    return response(200, {'items': items[:limit], 'count': min(len(items), limit)})


def get_task(event: dict[str, Any]) -> dict[str, Any]:
    task_id = require_path_param(event, 'id')
    item = OPERATIONAL_TASKS_TABLE.get_item(Key={'taskId': task_id}).get('Item')
    if not item:
        return response(404, {'message': 'Task not found'})
    return response(200, {'item': item})


def patch_task(event: dict[str, Any]) -> dict[str, Any]:
    task_id = require_path_param(event, 'id')
    existing = OPERATIONAL_TASKS_TABLE.get_item(Key={'taskId': task_id}).get('Item')
    if not existing:
        return response(404, {'message': 'Task not found'})

    payload = decode_body(event)
    if not isinstance(payload, dict):
        raise ValueError('Task patch payload must be an object')

    updated = dict(existing)
    updated.update(payload)
    updated['taskId'] = task_id
    updated['updatedAt'] = now_iso()
    OPERATIONAL_TASKS_TABLE.put_item(Item=to_dynamo_value(updated))
    return response(200, {'message': 'Task updated', 'item': updated})
