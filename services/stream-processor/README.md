# Stream Processor

Future work.

This service will later own the stateful video-processing flow:

```text
phone camera/frame input
  -> call services/inference POST /invocations
  -> ByteTrack
  -> zone analysis
  -> metrics/incidents
  -> backend writes
```

Do not place this logic inside the YOLO inference service. `services/inference` returns person boxes only.
