import { useMemo } from 'react';
import { DetectionFrame } from '../types';

/**
 * Binary search (lower bound) for sorted detection frames by timestamp in O(log N).
 */
function findClosestDetectionIndex(frames: DetectionFrame[], targetTime: number): number {
  if (!frames.length) return -1;
  let low = 0;
  let high = frames.length - 1;

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    if (frames[mid].t < targetTime) {
      low = mid + 1;
    } else if (frames[mid].t > targetTime) {
      high = mid - 1;
    } else {
      return mid;
    }
  }

  if (low >= frames.length) return frames.length - 1;
  if (high < 0) return 0;

  const diffLow = Math.abs(frames[low].t - targetTime);
  const diffHigh = Math.abs(frames[high].t - targetTime);
  return diffLow < diffHigh ? low : high;
}

export function useDetectionFrame(frames: DetectionFrame[], currentTime: number, maxDiffSec: number = 8.5): DetectionFrame | null {
  return useMemo(() => {
    if (!frames || !frames.length) return null;

    const idx = findClosestDetectionIndex(frames, currentTime);
    if (idx === -1) return null;

    const frame = frames[idx];
    if (Math.abs(frame.t - currentTime) <= maxDiffSec) {
      return frame;
    }
    return null;
  }, [frames, currentTime, maxDiffSec]);
}
