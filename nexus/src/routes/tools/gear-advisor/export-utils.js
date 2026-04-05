// @ts-nocheck
/**
 * Table export helpers — CSV, JSON, and PNG.
 *
 * All exporters trigger a browser download of `{filename}.{ext}`.
 * PNG export uses a plain 2D canvas drawing so no extra dependencies are
 * required; output is a compact tabular rendering that matches the HTML
 * table's logical structure but not its CSS styling.
 */

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Revoke after the click has had time to start the download.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Escape a single CSV cell value per RFC 4180. */
function csvCell(v) {
  if (v == null) return '';
  const s = String(v);
  if (s.includes('"') || s.includes(',') || s.includes('\n') || s.includes('\r')) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

/**
 * @param {string} filename — without extension
 * @param {string[]} headers — flat header row
 * @param {Array<Array<string|number|null>>} rows — data rows
 */
export function exportCSV(filename, headers, rows) {
  const lines = [headers.map(csvCell).join(',')];
  for (const row of rows) {
    lines.push(row.map(csvCell).join(','));
  }
  // Prepend BOM for Excel Unicode compatibility.
  const blob = new Blob(['\ufeff' + lines.join('\r\n')], {
    type: 'text/csv;charset=utf-8;'
  });
  downloadBlob(blob, filename + '.csv');
}

/**
 * @param {string} filename — without extension
 * @param {*} data — any JSON-serializable value
 */
export function exportJSON(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: 'application/json'
  });
  downloadBlob(blob, filename + '.json');
}

/**
 * Render a table as a PNG image via canvas. Supports a two-row header when
 * `headerRows` is a 2D array (first row can contain spans via { text, span }).
 *
 * @param {string} filename — without extension
 * @param {Array<Array<string | { text: string, span?: number }>>} headerRows
 * @param {Array<Array<string|number|null>>} rows
 * @param {object} [options]
 * @param {string} [options.title] — drawn above the table
 * @param {string[]} [options.numericCols] — column indices styled right-aligned
 */
export function exportTableAsImage(filename, headerRows, rows, options = {}) {
  const { title = '', numericCols = [] } = options;
  const numericSet = new Set(numericCols);

  const dpr = Math.max(1, window.devicePixelRatio || 1);
  const fontHeader = '600 11px system-ui, -apple-system, Segoe UI, sans-serif';
  const fontBody = '12px system-ui, -apple-system, Segoe UI, sans-serif';
  const fontTitle = '600 14px system-ui, -apple-system, Segoe UI, sans-serif';
  const padX = 10;
  const rowH = 22;
  const headerH = 24;
  const titleH = title ? 28 : 0;
  const borderColor = '#3a3f4b';
  const headerBg = '#1f232c';
  const evenRowBg = 'rgba(31, 35, 44, 0.3)';
  const textColor = '#e5e7eb';
  const mutedColor = '#9ca3af';

  // Flatten last row of headers to determine per-column widths.
  const flatHeaders = headerRows[headerRows.length - 1].map(h =>
    typeof h === 'string' ? h : h.text
  );
  const colCount = flatHeaders.length;

  // Measure canvas required (using an off-screen canvas for measurement).
  const measureCanvas = document.createElement('canvas');
  const mctx = measureCanvas.getContext('2d');
  const colWidths = new Array(colCount).fill(0);

  function measureWidth(text, font) {
    mctx.font = font;
    return mctx.measureText(String(text ?? '')).width;
  }

  for (let c = 0; c < colCount; c++) {
    colWidths[c] = Math.max(colWidths[c], measureWidth(flatHeaders[c], fontHeader));
  }
  // Top header row can have spans — measure spanned text against span width.
  if (headerRows.length > 1) {
    const topRow = headerRows[0];
    let col = 0;
    for (const cell of topRow) {
      const text = typeof cell === 'string' ? cell : cell.text;
      const span = typeof cell === 'string' ? 1 : (cell.span || 1);
      const w = measureWidth(text, fontHeader);
      // Distribute extra width across spanned columns if needed.
      const currentSpanWidth = colWidths.slice(col, col + span).reduce((a, b) => a + b, 0)
        + (span - 1) * padX * 2;
      if (w > currentSpanWidth) {
        const extra = (w - currentSpanWidth) / span;
        for (let i = 0; i < span; i++) colWidths[col + i] += extra;
      }
      col += span;
    }
  }
  for (const row of rows) {
    for (let c = 0; c < colCount; c++) {
      colWidths[c] = Math.max(colWidths[c], measureWidth(row[c], fontBody));
    }
  }
  // Add cell padding.
  for (let c = 0; c < colCount; c++) colWidths[c] += padX * 2;

  const tableW = colWidths.reduce((a, b) => a + b, 0);
  const totalHeaderH = headerH * headerRows.length;
  const tableH = totalHeaderH + rows.length * rowH;
  const canvasW = tableW;
  const canvasH = titleH + tableH;

  // Draw
  const canvas = document.createElement('canvas');
  canvas.width = canvasW * dpr;
  canvas.height = canvasH * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);

  // Background
  ctx.fillStyle = '#14171e';
  ctx.fillRect(0, 0, canvasW, canvasH);

  // Title
  if (title) {
    ctx.font = fontTitle;
    ctx.fillStyle = textColor;
    ctx.textBaseline = 'middle';
    ctx.fillText(title, padX, titleH / 2);
  }

  const yStart = titleH;

  // Header background
  ctx.fillStyle = headerBg;
  ctx.fillRect(0, yStart, canvasW, totalHeaderH);

  // Header text
  ctx.font = fontHeader;
  ctx.fillStyle = mutedColor;
  ctx.textBaseline = 'middle';
  if (headerRows.length === 1) {
    // single header row
    let x = 0;
    for (let c = 0; c < colCount; c++) {
      const w = colWidths[c];
      ctx.textAlign = numericSet.has(c) ? 'right' : 'left';
      const tx = numericSet.has(c) ? x + w - padX : x + padX;
      ctx.fillText(String(flatHeaders[c] ?? ''), tx, yStart + headerH / 2);
      x += w;
    }
  } else {
    // two-row header: top row may contain spans
    const topRow = headerRows[0];
    let x = 0;
    let col = 0;
    for (const cell of topRow) {
      const text = typeof cell === 'string' ? cell : cell.text;
      const span = typeof cell === 'string' ? 1 : (cell.span || 1);
      const w = colWidths.slice(col, col + span).reduce((a, b) => a + b, 0);
      ctx.textAlign = 'center';
      ctx.fillText(String(text ?? ''), x + w / 2, yStart + headerH / 2);
      // Draw a vertical separator between spans
      if (col + span < colCount) {
        ctx.strokeStyle = borderColor;
        ctx.beginPath();
        ctx.moveTo(x + w, yStart);
        ctx.lineTo(x + w, yStart + totalHeaderH);
        ctx.stroke();
      }
      x += w;
      col += span;
    }
    // Separator between top and bottom header rows
    ctx.strokeStyle = borderColor;
    ctx.beginPath();
    ctx.moveTo(0, yStart + headerH);
    ctx.lineTo(canvasW, yStart + headerH);
    ctx.stroke();
    // Bottom row
    x = 0;
    for (let c = 0; c < colCount; c++) {
      const w = colWidths[c];
      ctx.textAlign = numericSet.has(c) ? 'right' : 'left';
      const tx = numericSet.has(c) ? x + w - padX : x + padX;
      ctx.fillText(String(flatHeaders[c] ?? ''), tx, yStart + headerH + headerH / 2);
      x += w;
    }
  }

  // Rows
  ctx.font = fontBody;
  for (let r = 0; r < rows.length; r++) {
    const y = yStart + totalHeaderH + r * rowH;
    if (r % 2 === 1) {
      ctx.fillStyle = evenRowBg;
      ctx.fillRect(0, y, canvasW, rowH);
    }
    ctx.fillStyle = textColor;
    let x = 0;
    for (let c = 0; c < colCount; c++) {
      const w = colWidths[c];
      ctx.textAlign = numericSet.has(c) ? 'right' : 'left';
      const tx = numericSet.has(c) ? x + w - padX : x + padX;
      const val = rows[r][c];
      ctx.fillText(val == null ? '—' : String(val), tx, y + rowH / 2);
      x += w;
    }
  }

  // Outer border
  ctx.strokeStyle = borderColor;
  ctx.lineWidth = 1;
  ctx.strokeRect(0.5, yStart + 0.5, canvasW - 1, tableH - 1);

  canvas.toBlob(blob => {
    if (blob) downloadBlob(blob, filename + '.png');
  }, 'image/png');
}
