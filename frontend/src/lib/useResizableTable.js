// useResizableTable
// Lightweight, dependency-free column-width + row-height resizing for tables.
// Column widths live in React state and are applied via a <colgroup>; row
// heights live in a keyed map and are applied via per-row style. The drag
// start size is read directly from the DOM (the header cell / row), so there
// is no ref-during-render and re-renders never fight the values.
//
// Usage in a component:
//   const rt = useResizableTable([64, 112, 56]);
//   <table className="fp-rt">
//     <colgroup>{rt.cols.map((w,i)=><col key={i} style={{width:w}}/>)}</colgroup>
//     <thead><tr>
//       <th className="relative">Layer
//         <span className="fp-col-grip" onPointerDown={e=>rt.startColResize(0,e)} />
//       </th> ...
//     </tr></thead>
//     <tbody>{rows.map((r,ri)=>(
//       <tr key={ri} style={rt.rowH[ri]?{height:rt.rowH[ri]}:undefined}>
//         <td className="relative">...
//           <span className="fp-row-grip" onPointerDown={e=>rt.startRowResize(ri,e)} />
//         </td> ...
//       </tr>))}
//     </tbody>
//   </table>

import { useState, useCallback } from "react";

export function useResizableTable(initialColWidths, opts = {}) {
  const minCol = opts.minCol ?? 40;
  const minRow = opts.minRow ?? 24;
  const [cols, setCols] = useState(initialColWidths);
  const [rowH, setRowH] = useState({}); // rowKey -> px height

  const startColResize = useCallback((i, ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    // The grip lives inside the <th>; read its current width from the DOM.
    const th = ev.currentTarget.parentElement;
    const startW = th ? th.getBoundingClientRect().width : 80;
    const startX = ev.clientX;
    const onMove = (e) => {
      const w = Math.max(minCol, startW + (e.clientX - startX));
      setCols((prev) => { const n = [...prev]; n[i] = w; return n; });
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }, [minCol]);

  const startRowResize = useCallback((rowKey, ev) => {
    ev.preventDefault();
    ev.stopPropagation();
    // The grip lives inside a <td>; read the row's current height from the DOM.
    const tr = ev.currentTarget.closest("tr");
    const startH = tr ? tr.getBoundingClientRect().height : minRow;
    const startY = ev.clientY;
    const onMove = (e) => {
      const h = Math.max(minRow, startH + (e.clientY - startY));
      setRowH((prev) => ({ ...prev, [rowKey]: h }));
    };
    const onUp = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
  }, [minRow]);

  return { cols, setCols, rowH, startColResize, startRowResize };
}
