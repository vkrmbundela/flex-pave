import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
    },
  },
  {
    // Web Workers run in their own global scope (importScripts, self) and the
    // Pyodide CDN script injects loadPyodide.
    files: ['**/*.worker.js'],
    languageOptions: {
      globals: { ...globals.worker, loadPyodide: 'readonly' },
    },
  },
  {
    // Build/tooling config files run under Node.
    files: ['*.config.js'],
    languageOptions: {
      globals: globals.node,
    },
  },
])
