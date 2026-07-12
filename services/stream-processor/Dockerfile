FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TRACK_FRAME_RATE=30 \
    YOLO_CONFIG_DIR=/tmp

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

RUN mkdir -p /tmp/Ultralytics \
    && printf '%s\n' \
    '{' \
    '  "settings_version": "0.0.6",' \
    '  "datasets_dir": "/tmp/datasets",' \
    '  "weights_dir": "/tmp/weights",' \
    '  "runs_dir": "/tmp/runs",' \
    '  "uuid": "0000000000000000000000000000000000000000000000000000000000000000",' \
    '  "sync": false,' \
    '  "api_key": "",' \
    '  "openai_api_key": "",' \
    '  "clearml": false,' \
    '  "comet": false,' \
    '  "dvc": false,' \
    '  "hub": false,' \
    '  "mlflow": false,' \
    '  "neptune": false,' \
    '  "raytune": false,' \
    '  "tensorboard": false,' \
    '  "wandb": false,' \
    '  "vscode_msg": false,' \
    '  "openvino_msg": false' \
    '}' > /tmp/Ultralytics/settings.json

COPY app ./app
COPY scripts ./scripts

EXPOSE 8090

RUN printf '%s\n' \
    '#!/usr/bin/env sh' \
    'set -eu' \
    'if [ "${PROCESSOR_MODE:-api}" = "worker" ]; then' \
    '  if [ -z "${VIDEO_SOURCE:-}" ]; then' \
    '    echo "PROCESSOR_MODE=worker but VIDEO_SOURCE is empty; running standby loop."' \
    '    while true; do sleep 300; done' \
    '  fi' \
    '  exec python scripts/run-detection-loop.py' \
    'fi' \
    'exec uvicorn app.main:app --host 0.0.0.0 --port 8090' \
    > /usr/local/bin/processor-entrypoint \
    && chmod +x /usr/local/bin/processor-entrypoint

CMD ["/usr/local/bin/processor-entrypoint"]
