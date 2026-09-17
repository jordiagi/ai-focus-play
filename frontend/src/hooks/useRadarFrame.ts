import { useMemo } from 'react';
import { RadarFrame } from '../types';

/**
 * Binary search (lower bound) for sorted radar frames by timestamp in O(log N).
 */
function findClosestFrameIndex(frames: RadarFrame[], targetTime: number): number {
  if (!frames.length) return -1;
  let low = 0;
  let high = frames.length - 1;

  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    if (frames[mid].timestamp < targetTime) {
      low = mid + 1;
    } else if (frames[mid].timestamp > targetTime) {
      high = mid - 1;
    } else {
      return mid;
    }
  }

  // low and high are the adjacent indices
  if (low >= frames.length) return frames.length - 1;
  if (high < 0) return 0;

  const diffLow = Math.abs(frames[low].timestamp - targetTime);
  const diffHigh = Math.abs(frames[high].timestamp - targetTime);
  return diffLow < diffHigh ? low : high;
}

export function useRadarFrame(frames: RadarFrame[], currentTime: number) {
  return useMemo(() => {
    if (!frames.length) {
      return { currentFrame: null, historyFrames: [] };
    }

    const idx = findClosestFrameIndex(frames, currentTime);
    if (idx === -1) {
      return { currentFrame: null, historyFrames: [] };
    }

    const currentFrame = frames[idx];

    // Efficiently slice history frames in window [currentTime - 2.5, currentTime]
    const historyFrames: RadarFrame[] = [];
    const minTime = currentTime - 2.5;

    for (let i = idx; i >= 0; i--) {
      if (frames[i].timestamp < minTime) break;
      if (frames[i].timestamp <= currentTime) {
        historyFrames.unshift(frames[i]);
      }
    }

    return { currentFrame, historyFrames };
  }, [frames, currentTime]);
}
