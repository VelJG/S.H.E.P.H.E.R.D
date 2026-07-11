import argparse
from pathlib import Path

import requests


def main() -> None:
    parser = argparse.ArgumentParser(description="Invoke local S.H.E.P.H.E.R.D. YOLO inference service.")
    parser.add_argument("--image", required=True, help="Path to an image file.")
    parser.add_argument("--url", default="http://localhost:8080/invocations", help="Inference endpoint URL.")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        raise SystemExit(f"Image not found: {image_path}")

    with image_path.open("rb") as image_file:
        response = requests.post(args.url, files={"file": (image_path.name, image_file)}, timeout=60)

    response.raise_for_status()
    print(response.text)


if __name__ == "__main__":
    main()
