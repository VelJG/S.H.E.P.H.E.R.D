import base64
import json
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib import error as urlerror
from urllib.parse import unquote_plus
from urllib.request import Request, urlopen

import boto3
from boto3.dynamodb.conditions import Key


dynamodb = boto3.resource('dynamodb')
s3_client = boto3.client('s3')
sagemaker_runtime = boto3.client('sagemaker-runtime')
bedrock_runtime = boto3.client('bedrock-runtime')

VENUE_METRICS_TABLE = dynamodb.Table(os.environ['VENUE_METRICS_TABLE'])
INCIDENTS_TABLE = dynamodb.Table(os.environ['INCIDENTS_TABLE'])
OPERATIONAL_TASKS_TABLE = dynamodb.Table(os.environ['OPERATIONAL_TASKS_TABLE'])
CONFIG_ZONES_TABLE = dynamodb.Table(os.environ['CONFIG_ZONES_TABLE'])
AGENT_ALERTS_TABLE = dynamodb.Table(os.environ['AGENT_ALERTS_TABLE'])
EVIDENCE_BUCKET_NAME = os.environ['EVIDENCE_BUCKET_NAME']
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL', '').strip()
SAGEMAKER_ENDPOINT_NAME = os.environ.get('SAGEMAKER_ENDPOINT_NAME', '').strip()
AGENT_AI_PROVIDER = os.environ.get('AGENT_AI_PROVIDER', 'bedrock').strip().lower()
BEDROCK_MODEL_ID = os.environ.get('BEDROCK_MODEL_ID', 'anthropic.claude-3-haiku-20240307-v1:0').strip()


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
        if route_key == 'POST /demo/infer-frame':
            return post_demo_infer_frame(event)
        if route_key == 'POST /demo/track':
            return post_demo_track(event)
        if route_key == 'POST /demo/reset':
            return response(200, {'ok': True})
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
        if route_key == 'POST /agent/chat':
            return post_agent_chat(event)
        if route_key == 'GET /agent/report':
            return get_agent_report(event)
        if route_key == 'GET /agent/alerts':
            return list_agent_alerts(event)
        if route_key == 'POST /agent/monitor/run':
            return post_agent_monitor_run(event)
        if route_key == 'POST /agent/ingest/metrics':
            return post_agent_ingest_metrics(event)
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


def positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f'`{field_name}` must be a positive integer')
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'`{field_name}` must be a positive integer') from None
    if parsed <= 0:
        raise ValueError(f'`{field_name}` must be a positive integer')
    return parsed


def number_value(value: Any, field_name: str) -> int | float:
    if isinstance(value, bool):
        raise ValueError(f'`{field_name}` must be a number')
    if isinstance(value, (int, float)):
        return value
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f'`{field_name}` must be a number') from None
    if parsed.is_integer():
        return int(parsed)
    return parsed


def normalize_point(point: Any, zone_index: int, point_index: int) -> list[int | float]:
    field_name = f'zones[{zone_index}].points[{point_index}]'

    if isinstance(point, list) and len(point) == 2:
        return [
            number_value(point[0], f'{field_name}[0]'),
            number_value(point[1], f'{field_name}[1]'),
        ]

    if isinstance(point, dict) and 'x' in point and 'y' in point:
        return [
            number_value(point['x'], f'{field_name}.x'),
            number_value(point['y'], f'{field_name}.y'),
        ]

    raise ValueError(f'`{field_name}` must be [x, y] or {{ "x": number, "y": number }}')


def normalize_zone(zone: Any, index: int) -> dict[str, Any]:
    if not isinstance(zone, dict):
        raise ValueError(f'`zones[{index}]` must be an object')

    points = zone.get('points')
    if not isinstance(points, list):
        raise ValueError(f'`zones[{index}].points` must be an array')
    if len(points) < 3:
        raise ValueError(f'`zones[{index}].points` must contain at least 3 points')

    zone_id = zone.get('id') or zone.get('zoneId')
    if not zone_id:
        raise ValueError(f'`zones[{index}].id` is required')

    normalized = {
        'id': str(zone_id),
        'name': str(zone.get('name', zone_id)),
        'warnAt': positive_int(zone.get('warnAt', 4), f'zones[{index}].warnAt'),
        'congestAt': positive_int(zone.get('congestAt', 7), f'zones[{index}].congestAt'),
        'avgServiceSec': positive_int(zone.get('avgServiceSec', 20), f'zones[{index}].avgServiceSec'),
        'points': [normalize_point(point, index, point_index) for point_index, point in enumerate(points)],
    }

    for optional_field in ('color', 'description'):
        if optional_field in zone:
            normalized[optional_field] = zone[optional_field]

    return normalized


def normalize_zone_config(payload: Any) -> dict[str, Any]:
    if isinstance(payload, list):
        raw_zones = payload
        frame_width = None
        frame_height = None
        updated_by = 'dashboard'
        updated_at = now_iso()
    elif isinstance(payload, dict):
        raw_zones = payload.get('zones')
        frame_width = payload.get('frameWidth')
        frame_height = payload.get('frameHeight')
        updated_by = payload.get('updatedBy', 'dashboard')
        updated_at = payload.get('updatedAt', now_iso())
    else:
        raise ValueError('Config payload must be a JSON object or array')

    if not isinstance(raw_zones, list):
        raise ValueError('`zones` must be an array')

    return {
        'configId': 'default',
        'frameWidth': positive_int(frame_width, 'frameWidth') if frame_width is not None else None,
        'frameHeight': positive_int(frame_height, 'frameHeight') if frame_height is not None else None,
        'zones': [normalize_zone(zone, index) for index, zone in enumerate(raw_zones)],
        'updatedAt': str(updated_at),
        'updatedBy': str(updated_by),
    }


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


def text_value(value: Any, fallback: str = 'unknown') -> str:
    if value in (None, ''):
        return fallback
    return str(value)


def event_headers(event: dict[str, Any]) -> dict[str, str]:
    return {str(key).lower(): str(value) for key, value in (event.get('headers') or {}).items()}


def raw_body_bytes(event: dict[str, Any]) -> bytes:
    body = event.get('body') or ''
    if event.get('isBase64Encoded'):
        return base64.b64decode(body)
    return body.encode('utf-8')


def post_demo_infer_frame(event: dict[str, Any]) -> dict[str, Any]:
    if not SAGEMAKER_ENDPOINT_NAME:
        raise ValueError('SAGEMAKER_ENDPOINT_NAME is not configured')

    headers = event_headers(event)
    content_type = headers.get('content-type', '')
    if not content_type.startswith('multipart/form-data'):
        raise ValueError('Expected multipart/form-data with a file field')

    invoke_response = sagemaker_runtime.invoke_endpoint(
        EndpointName=SAGEMAKER_ENDPOINT_NAME,
        Body=raw_body_bytes(event),
        ContentType=content_type,
        Accept='application/json',
    )
    payload = invoke_response['Body'].read().decode('utf-8')
    return response(200, json.loads(payload))


def post_demo_track(event: dict[str, Any]) -> dict[str, Any]:
    payload = decode_body(event)
    if not isinstance(payload, dict):
        raise ValueError('Demo track payload must be an object')

    detections = payload.get('detections') if isinstance(payload.get('detections'), list) else []
    zones = payload.get('zones') if isinstance(payload.get('zones'), list) else []

    tracks = []
    for index, detection in enumerate(detections):
        if int(detection.get('class_id', 0)) != 0:
            continue
        bbox = [round(float(value), 2) for value in detection.get('bbox_xyxy', [])[:4]]
        if len(bbox) != 4:
            continue
        tracks.append({
            'id': index + 1,
            'track_id': index + 1,
            'bbox_xyxy': bbox,
            'confidence': round(float(detection.get('confidence', 0)), 4),
            'class_id': 0,
            'class_name': 'person',
        })

    metrics = []
    for zone in zones:
        zone_id = str(zone.get('id', 'unknown'))
        points = parse_zone_points(zone.get('points'))
        warn_at = int(zone.get('warnAt', zone.get('warn_at', 4)))
        congest_at = int(zone.get('congestAt', zone.get('congest_at', 7)))
        avg_service_sec = int(zone.get('avgServiceSec', zone.get('avg_service_sec', 20)))
        count = sum(point_in_polygon(foot_point(track['bbox_xyxy']), points) for track in tracks)
        status = 'congested' if count >= congest_at else 'warning' if count >= warn_at else 'normal'
        metrics.append({
            'zoneId': zone_id,
            'personCount': count,
            'queueLength': count,
            'waitSec': count * avg_service_sec,
            'status': status,
        })

    return response(200, {'tracks': tracks, 'zones': metrics})


def parse_zone_points(value: Any) -> list[tuple[float, float]]:
    points = []
    if not isinstance(value, list):
        return points
    for point in value:
        if isinstance(point, dict):
            points.append((float(point['x']), float(point['y'])))
        elif isinstance(point, list) and len(point) >= 2:
            points.append((float(point[0]), float(point[1])))
    return points


def foot_point(bbox: list[float]) -> tuple[float, float]:
    x1, _, x2, y2 = bbox
    return ((x1 + x2) / 2, y2)


def point_in_polygon(point: tuple[float, float], polygon: list[tuple[float, float]]) -> bool:
    if len(polygon) < 3:
        return False
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i in range(len(polygon)):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def discord_notification_payload(incident: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    metrics = incident.get('metrics', {})
    if not isinstance(metrics, dict):
        metrics = {}

    zone_id = text_value(incident.get('zoneId'))
    severity = text_value(incident.get('severity'), 'medium')
    person_count = text_value(
        incident.get('personCount', metrics.get('personCount', metrics.get('queueLength', 'n/a'))),
        'n/a',
    )
    status = text_value(metrics.get('status', incident.get('status')), 'open')
    wait_sec = text_value(metrics.get('waitSec'), 'n/a')

    return {
        'username': 'SHEPHERD Alerts',
        'content': f'Congestion detected in `{zone_id}`.',
        'allowed_mentions': {'parse': []},
        'embeds': [
            {
                'title': 'Hottest Zone Alert',
                'description': text_value(incident.get('summary'), 'A monitored zone is crowded and requires attention.'),
                'color': 15620935,
                'fields': [
                    {'name': 'Zone', 'value': zone_id, 'inline': True},
                    {'name': 'Severity', 'value': severity, 'inline': True},
                    {'name': 'People', 'value': person_count, 'inline': True},
                    {'name': 'Status', 'value': status, 'inline': True},
                    {'name': 'Wait', 'value': f'{wait_sec}s' if wait_sec != 'n/a' else 'n/a', 'inline': True},
                    {'name': 'Task', 'value': text_value(task.get('taskId')), 'inline': True},
                ],
                'footer': {'text': f"Incident {text_value(incident.get('incidentId'))}"},
                'timestamp': text_value(incident.get('createdAt'), now_iso()),
            },
        ],
    }


def send_discord_incident_notification(incident: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    if not DISCORD_WEBHOOK_URL:
        return {'status': 'skipped', 'reason': 'DISCORD_WEBHOOK_URL not configured'}

    payload = discord_notification_payload(incident, task)
    data = json.dumps(payload, default=json_default).encode('utf-8')
    request = Request(
        DISCORD_WEBHOOK_URL,
        data=data,
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'SHEPHERD-Lambda/0.1',
        },
        method='POST',
    )

    try:
        with urlopen(request, timeout=5) as result:
            return {'status': 'sent', 'statusCode': result.status}
    except urlerror.HTTPError as exc:
        print(f'Discord notification failed with HTTP {exc.code}')
        return {'status': 'failed', 'statusCode': exc.code}
    except urlerror.URLError as exc:
        print(f'Discord notification failed: {exc.reason}')
        return {'status': 'failed', 'reason': str(exc.reason)}
    except Exception as exc:
        print(f'Discord notification failed: {type(exc).__name__}')
        return {'status': 'failed', 'reason': type(exc).__name__}


def get_config_zones() -> dict[str, Any]:
    item = CONFIG_ZONES_TABLE.get_item(Key={'configId': 'default'}).get('Item', {})
    # `or` (not dict default) so a stored NULL frameWidth still falls back to
    # 1280x720 - the processor relies on these for coordinate scaling.
    return response(200, {
        'configId': 'default',
        'frameWidth': item.get('frameWidth') or 1280,
        'frameHeight': item.get('frameHeight') or 720,
        'zones': item.get('zones', []),
        'updatedAt': item.get('updatedAt'),
        'updatedBy': item.get('updatedBy'),
    })


def put_config_zones(event: dict[str, Any]) -> dict[str, Any]:
    payload = decode_body(event)
    item = normalize_zone_config(payload)
    CONFIG_ZONES_TABLE.put_item(Item=to_dynamo_value(item))
    return response(200, {
        'message': 'Zones updated',
        'item': item,
    })


def post_metrics(event: dict[str, Any]) -> dict[str, Any]:
    payload = decode_body(event)
    request_timestamp = now_iso()

    if isinstance(payload, list):
        metrics = payload
        default_timestamp = request_timestamp
    elif isinstance(payload, dict) and isinstance(payload.get('metrics'), list):
        metrics = payload['metrics']
        default_timestamp = payload.get('ts', payload.get('timestamp', request_timestamp))
    elif isinstance(payload, dict) and isinstance(payload.get('zones'), list):
        metrics = payload['zones']
        default_timestamp = payload.get('ts', payload.get('timestamp', request_timestamp))
    elif isinstance(payload, dict):
        metrics = [payload]
        default_timestamp = payload.get('ts', payload.get('timestamp', request_timestamp))
    else:
        raise ValueError('Metrics payload must be an object, array, `{ metrics: [...] }`, or `{ ts, zones: [...] }`')

    written = 0
    for metric in metrics:
        if not isinstance(metric, dict):
            raise ValueError('Each metric item must be an object')
        zone_id = metric.get('zoneId')
        if not zone_id:
            raise ValueError('Each metric item must include `zoneId`')

        item = {
            'zoneId': str(zone_id),
            'timestamp': str(metric.get('timestamp', metric.get('ts', default_timestamp))),
            'source': metric.get('source', 'processor'),
            'status': metric.get('status', 'normal'),
            'personCount': metric.get('personCount', metric.get('occupancy', 0)),
            'occupancy': metric.get('occupancy', metric.get('personCount', 0)),
            'queueLength': metric.get('queueLength', metric.get('personCount', 0)),
            'waitSec': metric.get('waitSec', 0),
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
    # merge extra payload fields (type, personCount, ...) but keep the nested
    # `task` request object out of the incident record - it becomes its own item
    incident_item.update({k: v for k, v in payload.items() if k not in incident_item and k != 'task'})
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

    discord_notification = (
        {'status': 'skipped', 'reason': 'notifyDiscord disabled'}
        if payload.get('notifyDiscord') is False
        else send_discord_incident_notification(incident_item, task_item)
    )

    return response(201, {
        'message': 'Incident created',
        'incident': incident_item,
        'task': task_item,
        'discordNotification': discord_notification,
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



def latest_metrics_items() -> list[dict[str, Any]]:
    items = scan_all(VENUE_METRICS_TABLE)
    latest_by_zone: dict[str, dict[str, Any]] = {}
    for item in items:
        zone_id = str(item.get('zoneId', ''))
        current = latest_by_zone.get(zone_id)
        if current is None or str(item.get('timestamp', '')) > str(current.get('timestamp', '')):
            latest_by_zone[zone_id] = item
    return sorted(latest_by_zone.values(), key=lambda item: str(item.get('zoneId', '')))


def agent_zone_config() -> list[dict[str, Any]]:
    item = CONFIG_ZONES_TABLE.get_item(Key={'configId': 'default'}).get('Item', {})
    zones = item.get('zones') if isinstance(item.get('zones'), list) else []
    if zones:
        return zones
    return [
        {'id': 'booth-1', 'name': 'Registration Booth', 'warnAt': 4, 'congestAt': 7, 'avgServiceSec': 18},
        {'id': 'booth-2', 'name': 'AI Demo Booth', 'warnAt': 4, 'congestAt': 7, 'avgServiceSec': 25},
        {'id': 'entrance', 'name': 'Main Entrance', 'warnAt': 8, 'congestAt': 12, 'avgServiceSec': 10},
    ]


def agent_predictions() -> list[dict[str, Any]]:
    metrics = {str(item.get('zoneId')): item for item in latest_metrics_items()}
    predictions = []
    for zone in agent_zone_config():
        zone_id = str(zone.get('id', zone.get('zoneId', 'unknown')))
        metric = metrics.get(zone_id, {})
        count = int(metric.get('personCount', metric.get('queueLength', 0)) or 0)
        warn_at = int(zone.get('warnAt', 4) or 4)
        congest_at = int(zone.get('congestAt', 7) or 7)
        remaining = max(0, congest_at - count)
        risk = 'high' if count >= congest_at else 'medium' if count >= warn_at else 'low'
        eta_seconds = 0 if risk == 'high' else remaining * int(zone.get('avgServiceSec', 20) or 20)
        zone_name = str(zone.get('name', zone_id))
        recommendation = (
            f'Send 1 staff member to {zone_name} now and redirect arrivals to a quieter zone.'
            if risk == 'high'
            else f'Keep {zone_name} on watch and prepare staff if the queue keeps growing.'
            if risk == 'medium'
            else f'No action needed for {zone_name}; keep normal monitoring.'
        )
        predictions.append({
            'zoneId': zone_id,
            'zoneName': zone_name,
            'risk': risk,
            'etaSeconds': eta_seconds,
            'reason': f'{zone_name} has {count}/{congest_at} people in the latest AWS metric.',
            'recommendation': recommendation,
        })
    rank = {'high': 0, 'medium': 1, 'low': 2}
    return sorted(predictions, key=lambda item: (rank.get(item['risk'], 9), item.get('etaSeconds') or 999999, item['zoneId']))


def invoke_bedrock_answer(question: str, fallback_answer: str, tool_context: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if AGENT_AI_PROVIDER != 'bedrock' or not BEDROCK_MODEL_ID:
        return fallback_answer, {'aiUsed': False, 'aiProvider': 'deterministic-fallback'}
    body = {
        'anthropic_version': 'bedrock-2023-05-31',
        'max_tokens': 420,
        'temperature': 0.2,
        'system': 'You are SHEPHERD, an AI venue-operations agent. Use only the provided tool JSON. Be concise and action-oriented.',
        'messages': [
            {
                'role': 'user',
                'content': (
                    f'Operator question: {question}\n\n'
                    f'Tool result JSON:\n{json.dumps(tool_context, default=json_default)}\n\n'
                    'Write the dispatcher-ready answer under 90 words.'
                ),
            },
        ],
    }
    try:
        result = bedrock_runtime.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType='application/json',
            accept='application/json',
            body=json.dumps(body).encode('utf-8'),
        )
        payload = json.loads(result['body'].read().decode('utf-8'))
        content = payload.get('content', [])
        answer = ''.join(part.get('text', '') for part in content if isinstance(part, dict)).strip()
        if answer:
            return answer, {'aiUsed': True, 'aiProvider': 'bedrock', 'aiModel': BEDROCK_MODEL_ID}
    except Exception as exc:
        print(f'Bedrock agent synthesis failed: {type(exc).__name__}: {exc}')
        return fallback_answer, {'aiUsed': False, 'aiProvider': 'deterministic-fallback', 'aiError': type(exc).__name__}
    return fallback_answer, {'aiUsed': False, 'aiProvider': 'deterministic-fallback'}


def agent_response(question: str, mode: str = 'auto') -> dict[str, Any]:
    predictions = agent_predictions()
    latest = latest_metrics_items()
    top = predictions[0] if predictions else None
    normalized = question.lower()
    intent = mode if mode in ('predict', 'copilot', 'report') else 'report' if any(term in normalized for term in ('report', 'summary', 'tóm tắt', 'shift')) else 'predict' if any(term in normalized for term in ('predict', 'tắc', 'congest', 'staff', 'nghẽn')) else 'copilot'
    if intent == 'report':
        fallback_answer = f'Shift summary: {len(latest)} active zones. Top risk: {top["zoneName"] if top else "n/a"}. Recommendation: {top["recommendation"] if top else "keep monitoring"}'
        used_tools = ['generate_shift_report', 'get_latest_metrics', 'predict_congestion']
    elif intent == 'predict':
        fallback_answer = f'{top["zoneName"]} ({top["zoneId"]}) is {top["risk"]} risk. {top["recommendation"]}' if top else 'No metrics available yet.'
        used_tools = ['predict_congestion', 'get_metric_history', 'recommend_staff_action']
    else:
        busiest = max(latest, key=lambda item: int(item.get('personCount', item.get('queueLength', 0)) or 0), default=None)
        fallback_answer = f'Busiest zone right now is {busiest.get("zoneId")} with {busiest.get("personCount", 0)} people.' if busiest else 'No metrics available yet.'
        used_tools = ['get_latest_metrics', 'list_open_incidents']
    context = {'intent': intent, 'usedTools': used_tools, 'predictions': predictions, 'latestMetrics': latest}
    answer, ai_metadata = invoke_bedrock_answer(question, fallback_answer, context)
    return {
        'answer': answer,
        'intent': intent,
        'usedTools': used_tools,
        'predictions': predictions,
        'metadata': {**context, **ai_metadata},
    }


def post_agent_chat(event: dict[str, Any]) -> dict[str, Any]:
    payload = decode_body(event)
    if not isinstance(payload, dict):
        raise ValueError('Agent chat payload must be an object')
    return response(200, agent_response(str(payload.get('message', '')), str(payload.get('mode', 'auto'))))


def get_agent_report(event: dict[str, Any]) -> dict[str, Any]:
    return response(200, agent_response('Generate shift report', 'report'))


def list_agent_alerts(event: dict[str, Any]) -> dict[str, Any]:
    params = query_params(event)
    status = params.get('status')
    limit = int(params.get('limit', '20'))
    if status:
        result = AGENT_ALERTS_TABLE.query(
            IndexName='status-createdAt-index',
            KeyConditionExpression=Key('status').eq(status),
            ScanIndexForward=False,
            Limit=limit,
        )
        items = result.get('Items', [])
    else:
        items = sorted_desc(scan_all(AGENT_ALERTS_TABLE), 'createdAt')[:limit]
    return response(200, {'ok': True, 'alerts': items})


def post_agent_monitor_run(event: dict[str, Any]) -> dict[str, Any]:
    predictions = agent_predictions()
    top = predictions[0] if predictions else None
    if not top or top.get('risk') != 'high':
        return response(200, {'ok': True, 'alert': None})
    existing = AGENT_ALERTS_TABLE.scan(
        FilterExpression='zoneId = :zoneId AND #status = :status',
        ExpressionAttributeNames={'#status': 'status'},
        ExpressionAttributeValues={':zoneId': top['zoneId'], ':status': 'open'},
        Limit=1,
    ).get('Items', [])
    if existing:
        return response(200, {'ok': True, 'alert': None})
    created_at = now_iso()
    alert = {
        'alertId': f'AGENT-{uuid.uuid4()}',
        'zoneId': top['zoneId'],
        'zoneName': top['zoneName'],
        'status': 'open',
        'severity': 'high',
        'createdAt': created_at,
        'etaSeconds': top.get('etaSeconds'),
        'reason': top.get('reason'),
        'recommendation': top.get('recommendation'),
        'usedTools': ['predict_congestion', 'recommend_staff_action', 'put_agent_alert'],
        'source': 'agent-monitor-lambda',
    }
    AGENT_ALERTS_TABLE.put_item(Item=to_dynamo_value(alert))
    return response(200, {'ok': True, 'alert': alert})


def post_agent_ingest_metrics(event: dict[str, Any]) -> dict[str, Any]:
    metrics_response = post_metrics(event)
    monitor_response = post_agent_monitor_run(event)
    monitor_body = json.loads(monitor_response.get('body', '{}'))
    metrics_body = json.loads(metrics_response.get('body', '{}'))
    return response(202, {'ok': True, 'count': metrics_body.get('count', 0), 'alert': monitor_body.get('alert')})

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
