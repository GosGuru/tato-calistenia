import { defineConfig } from 'vitest/config';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  plugins: [tailwindcss()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  esbuild: { jsx: 'automatic' },
  build: { sourcemap: false, emptyOutDir: false },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test-setup.js',
    clearMocks: true,
  },
});
