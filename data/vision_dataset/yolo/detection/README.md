# YOLO detection dataset (gameplay frames)

Scraped icons are **reference templates**, not detection labels.

## Label scoreboard / draft crops

1. Sample frames from `test/videos/*.mp4` every 1–2 seconds during draft and scoreboard views.
2. Draw bounding boxes around each hero icon slot.
3. Class = hero name (skin-agnostic) using `catalog.json` `yolo.hero_classes`.
4. Export YOLO format: `images/train`, `labels/train` (normalized xywh).

## Train (Ultralytics)

```bash
yolo classify train data=data/vision_dataset/yolo/data.yaml model=yolov8n-cls.pt epochs=50
# or detection after labeling:
yolo detect train data=path/to/detection.yaml model=yolov8n.pt epochs=100
```
