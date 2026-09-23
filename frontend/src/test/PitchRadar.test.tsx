import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PitchRadar } from '../components/PitchRadar/PitchRadar';
import type { RadarFrame } from '../types';

const frame: RadarFrame = {
  timestamp: 12,
  players: [],
  ball: { x: 23, y: 17, z: 0, detected: false },
};

// No players: the four static pitch circles are the only legitimate circles
// without a detected ball. Count geometry, not a styling class or the caption.
describe('PitchRadar measured ball positions', () => {
  it('draws no ball when detection is false and explains its absence', () => {
    const { container } = render(<PitchRadar currentFrame={frame} />);
    expect(container.querySelectorAll('circle')).toHaveLength(4);
    expect(container.querySelector('circle[cx="23"][cy="17"]')).toBeNull();
    expect(screen.getByText('Ball not detected')).toBeTruthy();
  });

  it('draws a detected ball at its measured coordinates', () => {
    const { container } = render(
      <PitchRadar currentFrame={{ ...frame, ball: { ...frame.ball, detected: true } }} />,
    );
    expect(container.querySelectorAll('circle')).toHaveLength(5);
    expect(container.querySelector('circle[cx="23"][cy="17"]')).not.toBeNull();
    expect(screen.queryByText('Ball not detected')).toBeNull();
  });

  it('removes the previous ball when the next frame loses detection', () => {
    const { container, rerender } = render(
      <PitchRadar currentFrame={{ ...frame, ball: { ...frame.ball, detected: true } }} />,
    );
    expect(container.querySelector('circle[cx="23"][cy="17"]')).not.toBeNull();
    rerender(<PitchRadar currentFrame={frame} />);
    expect(container.querySelectorAll('circle')).toHaveLength(4);
    expect(container.querySelector('circle[cx="23"][cy="17"]')).toBeNull();
  });
});
