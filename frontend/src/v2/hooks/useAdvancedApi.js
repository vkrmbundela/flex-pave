import { useState, useCallback } from 'react';
import { runAdvanced, getSolverMode } from '../../lib/solver-client';

const API_BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

// Hook for the advanced analysis panels (Sensitivity, Monte-Carlo, Reserve,
// Strain-Field). POST compute requests route through the shared solver client:
// in "browser" mode they run in-process via Pyodide (no backend required, so
// they work on the static GitHub-Pages deploy); in "backend" mode they POST to
// the FastAPI /api/v2 endpoints. The response shape is identical either way.
export default function useAdvancedApi() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const post = useCallback(async (path, body) => {
    setLoading(true);
    setError(null);
    try {
      const json = await runAdvanced(path, body);
      setData(json);
      return json;
    } catch (e) {
      setError(e && e.message ? e.message : String(e));
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  // GET is used only for the optional materials library. In browser mode there
  // is no backend to query, so return null and let the caller fall back to its
  // bundled material data.
  const get = useCallback(async (path) => {
    if (getSolverMode() === 'browser') return null;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/v2${path}`, {
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      return json;
    } catch (e) {
      setError(e && e.message ? e.message : String(e));
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  return { data, error, loading, get, post };
}
