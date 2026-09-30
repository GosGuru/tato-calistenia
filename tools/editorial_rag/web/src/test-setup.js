import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// jsdom has no layout/media observers; browser verification remains separate.
Object.defineProperty(window, 'matchMedia', { writable: true, value: query => ({
  matches: false, media: query, onchange: null,
  addEventListener() {}, removeEventListener() {}, addListener() {}, removeListener() {}, dispatchEvent() { return true; },
}) });
globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
Element.prototype.scrollTo = function () {};

afterEach(cleanup);
