// The canonical coordinate system is the SNAPSHOT's native resolution
// (naturalWidth x naturalHeight). Zone points are stored in ORIGINAL IMAGE
// PIXELS, so no matter how CSS resizes the displayed frame, clicks map back to
// the real frame coordinates the Python processor sees. Default matches a
// typical 720p phone-camera frame.
export const DEFAULT_FRAME_W = 1280;
export const DEFAULT_FRAME_H = 720;

/** The camera frame the zones are drawn against. `kind` decides the backdrop:
 *  a still image, a looping uploaded video, or the built-in scene (url null). */
export type Frame = { width: number; height: number; url: string | null; kind?: 'image' | 'video' };

export type Point = { x: number; y: number };

export type ZoneStatus = 'normal' | 'warning' | 'congested';

/** A manually drawn monitoring area (e.g. the queue in front of one gift booth). */
export type Zone = {
  id: string;
  name: string;
  color: string;
  points: Point[];
  /** queueLength at/above which the zone is WARNING */
  warnAt: number;
  /** queueLength at/above which the zone is CONGESTED */
  congestAt: number;
  /** average seconds to serve one person, used to estimate wait time */
  avgServiceSec: number;
};

/** Live measurement for a single zone at one tick. */
export type ZoneMetric = {
  zoneId: string;
  personCount: number;
  waitSec: number;
  status: ZoneStatus;
  heatMean?: number;
  heatMax?: number;
  activeTrackIds?: number[];
};

export type Track = {
  id: number;
  bbox_xyxy: [number, number, number, number];
  confidence: number;
  class_id: number;
};

export type Incident = {
  id: string;
  zoneId: string;
  zoneName: string;
  personCount: number;
  createdAt: number;
  status: 'open' | 'acknowledged' | 'resolved';
};
