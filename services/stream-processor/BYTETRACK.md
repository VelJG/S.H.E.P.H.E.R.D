# ByteTrack integration

Keep one `ByteTrackZoneProcessor` for the lifetime of a camera stream and
call `update` once for every YOLO response:

```python
from app.processor import ByteTrackZoneProcessor

processor = ByteTrackZoneProcessor()
result = processor.update(
    yolo_response["detections"],
    [{
        "id": "booth-1",
        "points": [[150, 300], [470, 300], [470, 690], [150, 690]],
        "warnAt": 4,
        "congestAt": 7,
        "avgServiceSec": 20,
    }],
)
```

`result["tracks"]` contains persistent `id` values and bounding boxes.
`result["zones"]` contains `personCount`, `waitSec`, and `status`.
The zone count uses each person's bottom-center bbox point.
