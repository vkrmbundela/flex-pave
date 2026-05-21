// Pyodide Web Worker
// Loads the native Burmister solver into a browser Python runtime and
// answers solve requests over postMessage. Keeps the main thread free
// while NumPy/SciPy churn through Hankel inversion.

importScripts("https://cdn.jsdelivr.net/pyodide/v0.27.4/full/pyodide.js");

let pyodideReady = null;
let pyBaseUrl = null; // set by the first message from the main thread

async function initPyodide() {
  self.postMessage({ type: "status", stage: "loading-runtime", message: "Downloading Python runtime..." });
  const pyodide = await loadPyodide({
    indexURL: "https://cdn.jsdelivr.net/pyodide/v0.27.4/full/",
  });

  self.postMessage({ type: "status", stage: "loading-packages", message: "Loading NumPy + SciPy..." });
  await pyodide.loadPackage(["numpy", "scipy"]);

  self.postMessage({ type: "status", stage: "loading-solver", message: "Loading Burmister solver..." });
  // pyBaseUrl is an absolute URL supplied by the main thread (it knows Vite's
  // BASE_URL). In dev: http://localhost:5173/py/  In Pages: .../flex-pave/py/
  const base = (pyBaseUrl || "/py/").replace(/\/?$/, "/");
  const solverUrl = base + "burmister.py";
  const resp = await fetch(solverUrl);
  if (!resp.ok) throw new Error("Failed to fetch solver source from " + solverUrl);
  const solverSrc = await resp.text();

  pyodide.FS.writeFile("/home/pyodide/burmister.py", solverSrc);
  pyodide.runPython("import sys; sys.path.insert(0, '/home/pyodide')");
  pyodide.runPython("import burmister");

  self.postMessage({ type: "status", stage: "ready", message: "Solver ready." });
  return pyodide;
}

async function getPyodide() {
  if (!pyodideReady) pyodideReady = initPyodide();
  return pyodideReady;
}

async function handleSolve(request) {
  const pyodide = await getPyodide();
  // Mirror the FastAPI /api/solve request shape and produce the same response.
  const payload = {
    layers: request.layers.map((l) => ({
      modulus: l.E,
      poisson: l.nu,
      thickness: l.h,
    })),
    load: {
      load: request.wheel_load,
      pressure: request.tire_pressure,
      is_dual: (request.wheel_type || "single").toLowerCase() === "dual",
      spacing: request.wheel_spacing ?? 310,
    },
    points: request.points.map((p) => ({ z: p.z, r: p.r })),
  };

  pyodide.globals.set("_req_json", JSON.stringify(payload));
  const responseJson = pyodide.runPython(`
import json
_req = json.loads(_req_json)
_raw = burmister.analyze_pavement(_req["layers"], _req["load"], _req["points"])
_out = []
_max_disp = 0.0
_max_eps_t = 0.0
_max_eps_c = 0.0
for i, r in enumerate(_raw):
    _out.append({
        "id": i,
        "z": _req["points"][i]["z"],
        "r": _req["points"][i]["r"],
        "sigma_z": r.get("sigma_z", 0.0),
        "sigma_r": r.get("sigma_r", 0.0),
        "sigma_t": r.get("sigma_t", 0.0),
        "tau_rz": r.get("tau_rz", 0.0),
        "disp_z": r.get("disp_z", 0.0),
        "disp_r": r.get("disp_r", 0.0),
        "eps_z": r.get("eps_z", 0.0),
        "eps_r": r.get("eps_r", 0.0),
        "eps_t": r.get("eps_t", 0.0),
    })
    if abs(r.get("disp_z", 0.0)) > _max_disp: _max_disp = abs(r["disp_z"])
    if abs(r.get("eps_t", 0.0)) > _max_eps_t: _max_eps_t = abs(r["eps_t"])
    if abs(r.get("eps_z", 0.0)) > abs(_max_eps_c): _max_eps_c = r["eps_z"]
json.dumps({"status": "success", "results": _out,
            "max_disp": _max_disp, "max_strain_t": _max_eps_t, "max_strain_c": _max_eps_c})
`);
  return JSON.parse(responseJson);
}

self.onmessage = async (event) => {
  const { id, type, payload, pyBaseUrl: incomingBase } = event.data || {};
  if (incomingBase && !pyBaseUrl) pyBaseUrl = incomingBase;
  try {
    if (type === "init") {
      await getPyodide();
      self.postMessage({ id, type: "init-done" });
    } else if (type === "solve") {
      const result = await handleSolve(payload);
      self.postMessage({ id, type: "solve-result", result });
    } else {
      self.postMessage({ id, type: "error", error: "Unknown message type: " + type });
    }
  } catch (err) {
    self.postMessage({ id, type: "error", error: err && err.message ? err.message : String(err) });
  }
};
