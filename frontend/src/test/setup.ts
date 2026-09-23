import { cleanup } from '@testing-library/react';
import { afterEach, beforeEach, expect, vi } from 'vitest';

beforeEach(() => {
  // These components receive literal props. Any unexpected network request is a bug.
  vi.stubGlobal('fetch', vi.fn(() => {
    throw new Error('Network access is forbidden in component tests');
  }));
});

afterEach(() => {
  try {
    // Check markup too: fabricated names must not hide in titles or aria-labels.
    for (const name of ['Eric Jordi', 'Diego Morales', 'Julian Vance']) {
      expect(document.body.innerHTML).not.toContain(name);
    }
    expect(fetch).not.toHaveBeenCalled();
  } finally {
    cleanup();
    vi.unstubAllGlobals();
  }
});
