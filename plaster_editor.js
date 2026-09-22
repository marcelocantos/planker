/* 2D plasterboard cutter for the shop sheet.
   Keep this in step with plaster.py. tests/js_plaster.js checks they match.
   The sample job is substituted when the page is generated. */
var SAMPLE = __SAMPLE_JOB__;
var STORAGE_KEY = "planker-plaster-edit-v2";
var LIMIT_SHEETS = 80;
var LIMIT_PANELS = 200;
var LIMIT_MM = 20000;
var ERR_SHEETS = "Too many sheets to lay out here (limit 80).";
var ERR_PANELS = "Too many panels to lay out here (limit 200).";
var ERR_MM = "Width and height must be from 1 to 20000 mm.";
var ERR_KERF = "Saw kerf must be a whole number of millimetres, 0 or more.";
var PANEL_COLOURS = [
  "#e0b15a", "#f0d2b0", "#b9cbb0", "#e7c2a8", "#cbbba6",
  "#a9c5c4", "#efd28a", "#d9c4b4", "#c9b4c4", "#c4c8b0"
];

function rect(x, y, w, h) {
  return {x: x, y: y, w: w, h: h};
}

function sortRects(rects) {
  return rects.slice().sort(function (a, b) {
    if (a.y !== b.y) return a.y - b.y;
    if (a.x !== b.x) return a.x - b.x;
    if (a.w !== b.w) return a.w - b.w;
    return a.h - b.h;
  });
}

function fits(free, pw, ph, kerf) {
  if (pw > free.w || ph > free.h) return false;
  var leftoverW = free.w - pw;
  var leftoverH = free.h - ph;
  if (leftoverW > 0 && leftoverW < kerf) return false;
  if (leftoverH > 0 && leftoverH < kerf) return false;
  return true;
}

function splitFree(free, pw, ph, kerf) {
  var leftoverW = free.w - pw;
  var leftoverH = free.h - ph;
  var kerfs = [];
  var frees = [];
  function band(length) {
    if (length <= 0) return [0, 0];
    return [kerf, length - kerf];
  }
  var kerfW, restW, kerfH, restH, parts;
  if (leftoverW < leftoverH) {
    parts = band(leftoverW);
    kerfW = parts[0];
    restW = parts[1];
    parts = band(leftoverH);
    kerfH = parts[0];
    restH = parts[1];
    if (kerfW) kerfs.push(rect(free.x + pw, free.y, kerfW, free.h));
    if (restW) frees.push(rect(free.x + pw + kerfW, free.y, restW, free.h));
    if (kerfH) kerfs.push(rect(free.x, free.y + ph, pw, kerfH));
    if (restH) frees.push(rect(free.x, free.y + ph + kerfH, pw, restH));
  } else {
    parts = band(leftoverW);
    kerfW = parts[0];
    restW = parts[1];
    parts = band(leftoverH);
    kerfH = parts[0];
    restH = parts[1];
    if (kerfH) kerfs.push(rect(free.x, free.y + ph, free.w, kerfH));
    if (restH) frees.push(rect(free.x, free.y + ph + kerfH, free.w, restH));
    if (kerfW) kerfs.push(rect(free.x + pw, free.y, kerfW, ph));
    if (restW) frees.push(rect(free.x + pw + kerfW, free.y, restW, ph));
  }
  return {kerfs: kerfs, frees: frees};
}

function orientations(panel) {
  var options = [{rotated: false, w: panel.w, h: panel.h}];
  if (!panel.grain && panel.w !== panel.h) {
    options.push({rotated: true, w: panel.h, h: panel.w});
  }
  return options;
}

function better(score, best) {
  for (var i = 0; i < score.length; i++) {
    if (score[i] < best[i]) return true;
    if (score[i] > best[i]) return false;
  }
  return false;
}

function pieceColor(id) {
  var hue = Math.round((id * 137.508) % 360);
  return "hsl(" + hue + ",48%,62%)";
}

function pieceRecord(panel, placed) {
  if (!panel.face) {
    if (placed) return {};
    return {w: panel.w, h: panel.h, grain: panel.grain};
  }
  var record = {
    id: panel.i,
    face: panel.face,
    name: panel.name,
    u: panel.u,
    v: panel.v
  };
  if (placed) return record;
  record.w = panel.w;
  record.h = panel.h;
  record.grain = panel.grain;
  return record;
}

function packJob(job) {
  var kerf = job.kerf_mm;
  if (typeof kerf !== "number" || kerf < 0 || kerf > LIMIT_MM || kerf !== Math.floor(kerf)) {
    return {error: ERR_KERF};
  }
  var sheetN = 0;
  var panelN = 0;
  var row;
  for (var s = 0; s < job.available.length; s++) {
    row = job.available[s];
    if (row.w < 1 || row.h < 1 || row.w > LIMIT_MM || row.h > LIMIT_MM) return {error: ERR_MM};
    sheetN += row.count;
  }
  for (var d = 0; d < job.desired.length; d++) {
    row = job.desired[d];
    if (row.w < 1 || row.h < 1 || row.w > LIMIT_MM || row.h > LIMIT_MM) return {error: ERR_MM};
    panelN += row.count;
  }
  if (sheetN > LIMIT_SHEETS) return {error: ERR_SHEETS};
  if (panelN > LIMIT_PANELS) return {error: ERR_PANELS};

  var sheets = [];
  var index = 1;
  job.available.forEach(function (stock) {
    for (var n = 0; n < stock.count; n++) {
      sheets.push({
        index: index,
        w: stock.w,
        h: stock.h,
        placements: [],
        kerfRects: [],
        free: [rect(0, 0, stock.w, stock.h)]
      });
      index += 1;
    }
  });

  var panels = [];
  var pieceI = 0;
  job.desired.forEach(function (panel) {
    for (var n = 0; n < panel.count; n++) {
      var item = {w: panel.w, h: panel.h, grain: !!panel.grain, i: pieceI};
      if (panel.face) {
        item.face = panel.face;
        item.name = panel.name || panel.face;
        item.u = panel.u;
        item.v = panel.v;
      }
      panels.push(item);
      pieceI += 1;
    }
  });
  panels.sort(function (a, b) {
    var aMax = Math.max(a.w, a.h);
    var bMax = Math.max(b.w, b.h);
    if (aMax !== bMax) return bMax - aMax;
    var aArea = a.w * a.h;
    var bArea = b.w * b.h;
    if (aArea !== bArea) return bArea - aArea;
    var aMin = Math.min(a.w, a.h);
    var bMin = Math.min(b.w, b.h);
    if (aMin !== bMin) return bMin - aMin;
    return a.i - b.i;
  });

  var unplaced = [];
  panels.forEach(function (panel) {
    var best = null;
    for (var sheetI = 0; sheetI < sheets.length; sheetI++) {
      var sheet = sheets[sheetI];
      for (var freeI = 0; freeI < sheet.free.length; freeI++) {
        var free = sheet.free[freeI];
        var options = orientations(panel);
        for (var o = 0; o < options.length; o++) {
          var option = options[o];
          if (!fits(free, option.w, option.h, kerf)) continue;
          var score = [
            free.w * free.h - option.w * option.h,
            sheet.placements.length ? 0 : 1,
            option.rotated ? 1 : 0,
            sheetI,
            free.y,
            free.x
          ];
          if (!best || better(score, best.score)) {
            best = {
              score: score,
              sheetI: sheetI,
              freeI: freeI,
              w: option.w,
              h: option.h,
              rotated: option.rotated
            };
          }
        }
      }
    }
    if (!best) {
      unplaced.push(pieceRecord(panel, false));
      return;
    }
    var chosen = sheets[best.sheetI];
    var placedFree = chosen.free.splice(best.freeI, 1)[0];
    var parts = splitFree(placedFree, best.w, best.h, kerf);
    chosen.kerfRects = chosen.kerfRects.concat(parts.kerfs);
    chosen.free = chosen.free.concat(parts.frees);
    var placed = {
      x: placedFree.x,
      y: placedFree.y,
      w: best.w,
      h: best.h,
      rotated: best.rotated,
      grain: panel.grain,
      source_w: panel.w,
      source_h: panel.h
    };
    var extra = pieceRecord(panel, true);
    Object.keys(extra).forEach(function (key) { placed[key] = extra[key]; });
    chosen.placements.push(placed);
  });

  return {
    error: "",
    kerf_mm: kerf,
    sheets: sheets.map(function (sheet) {
      return {
        index: sheet.index,
        w: sheet.w,
        h: sheet.h,
        used: sheet.placements.length > 0,
        placements: sheet.placements,
        kerf: sortRects(sheet.kerfRects),
        waste: sortRects(sheet.free)
      };
    }),
    unplaced: unplaced
  };
}

function commas(value) {
  var sign = value < 0 ? "-" : "";
  var text = String(Math.abs(Math.trunc(value)));
  var out = "";
  for (var i = 0; i < text.length; i++) {
    if (i > 0 && (text.length - i) % 3 === 0) out += ",";
    out += text.charAt(i);
  }
  return sign + out;
}

function areaM2(mm2) {
  var whole = Math.floor(mm2 / 1000000);
  var milli = Math.floor((mm2 % 1000000) / 1000);
  var frac = String(milli);
  while (frac.length < 3) frac = "0" + frac;
  return whole + "." + frac + " m2";
}

function sheetGroups(sheets, used) {
  var order = [];
  var counts = {};
  sheets.forEach(function (sheet) {
    if (sheet.used !== used) return;
    var key = sheet.w + "x" + sheet.h;
    if (!counts[key]) {
      counts[key] = {w: sheet.w, h: sheet.h, n: 0};
      order.push(key);
    }
    counts[key].n += 1;
  });
  return order.map(function (key) { return counts[key]; });
}

function panelGroups(panels) {
  var order = [];
  var counts = {};
  panels.forEach(function (panel) {
    var key = panel.w + "x" + panel.h + ":" + (panel.grain ? 1 : 0);
    if (!counts[key]) {
      counts[key] = {w: panel.w, h: panel.h, grain: panel.grain, n: 0};
      order.push(key);
    }
    counts[key].n += 1;
  });
  return order.map(function (key) { return counts[key]; });
}

function equation(sheet) {
  var panel = 0;
  var kerf = 0;
  var waste = 0;
  sheet.placements.forEach(function (item) { panel += item.w * item.h; });
  sheet.kerf.forEach(function (item) { kerf += item.w * item.h; });
  sheet.waste.forEach(function (item) { waste += item.w * item.h; });
  return commas(panel) + " + kerf " + commas(kerf) + " + offcut " + commas(waste) + " = " + commas(sheet.w * sheet.h) + " mm2";
}

function shopText(plan, job, custom) {
  if (plan.error) return plan.error + "\n";
  var banner = "Plasterboard job";
  if (custom) banner = "CUSTOM SIZES — edited on this phone, not a real job";
  else if (job.fictional) banner = "EXAMPLE / FICTIONAL — not a real job";
  else if (job.example) banner = "EXAMPLE — synthetic job, not a real bill of materials";
  var lines = [
    "PLANKER PLASTERBOARD",
    banner
  ];
  if (job.story && !custom) lines.push(job.story);
  lines.push(
    "Saw kerf: " + job.kerf_mm + " mm (setting kerf_mm). 0 mm is score-and-snap.",
    "Packing: guillotine best-area fit, shorter-leftover split. Not an exact optimum.",
    "",
    "PULL"
  );
  var pulls = sheetGroups(plan.sheets, true);
  if (pulls.length) {
    var totalN = 0;
    var totalArea = 0;
    pulls.forEach(function (group) {
      lines.push(group.n + " x " + group.w + " x " + group.h + " mm (" + areaM2(group.w * group.h) + " each)");
      totalN += group.n;
      totalArea += group.n * group.w * group.h;
    });
    lines.push("Total: " + totalN + " sheets, " + areaM2(totalArea));
  } else {
    lines.push("none");
  }
  lines.push("", "LEAVE");
  var leaves = sheetGroups(plan.sheets, false);
  if (leaves.length) {
    leaves.forEach(function (group) {
      lines.push(group.n + " x " + group.w + " x " + group.h + " mm (" + areaM2(group.w * group.h) + " each)");
    });
  } else {
    lines.push("none");
  }
  lines.push("", "DOES NOT FIT");
  if (plan.unplaced.length) {
    panelGroups(plan.unplaced).forEach(function (group) {
      var lock = group.grain ? "face locked" : "turns allowed";
      lines.push(group.n + " x " + group.w + " x " + group.h + " mm (" + lock + ")");
    });
    lines.push("These are panel sizes that did not fit. This list does not add a sheet to buy.");
  } else {
    lines.push("none");
  }
  lines.push("", "CUTS");
  var used = plan.sheets.filter(function (sheet) { return sheet.used; });
  if (!used.length) lines.push("none");
  used.forEach(function (sheet) {
    lines.push("Sheet " + sheet.index + " — " + sheet.w + " x " + sheet.h + " mm");
    sheet.placements.forEach(function (placement, index) {
      var extra = "";
      if (placement.rotated) extra = " turned (entered " + placement.source_w + " x " + placement.source_h + ")";
      else if (placement.grain) extra = " face locked";
      lines.push("  " + (index + 1) + ". " + placement.w + " x " + placement.h + " at " + placement.x + "," + placement.y + extra);
    });
    sheet.waste.forEach(function (offcut) {
      lines.push("  offcut " + offcut.w + " x " + offcut.h + " at " + offcut.x + "," + offcut.y);
    });
    if (job.kerf_mm && sheet.kerf.length) {
      var kerfArea = 0;
      sheet.kerf.forEach(function (item) { kerfArea += item.w * item.h; });
      lines.push("  kerf " + job.kerf_mm + " mm, " + areaM2(kerfArea));
    }
    lines.push("  " + equation(sheet));
  });
  lines.push("");
  return lines.join("\n");
}

function esc(value) {
  return String(value).replace(/[&<>"']/g, function (ch) {
    return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[ch];
  });
}

function mmSize(w, h) {
  return commas(w) + " × " + commas(h) + " mm";
}

function countLabel(count, one, many) {
  return count + " <small>" + (count === 1 ? one : many) + "</small>";
}

function areaLabel(mm2) {
  return areaM2(mm2).replace(" m2", " m²");
}

function sizeKey(panel) {
  var w = panel.source_w !== undefined ? panel.source_w : panel.w;
  var h = panel.source_h !== undefined ? panel.source_h : panel.h;
  return w + "x" + h + (panel.grain ? ":locked" : "");
}

function colourMap(plan) {
  var map = {};
  var n = 0;
  function take(panel) {
    if (typeof panel.id === "number") return;
    var key = sizeKey(panel);
    if (map[key]) return;
    map[key] = PANEL_COLOURS[n % PANEL_COLOURS.length];
    n += 1;
  }
  plan.sheets.forEach(function (sheet) {
    sheet.placements.forEach(take);
  });
  plan.unplaced.forEach(take);
  return map;
}

function fillFor(panel, colours) {
  if (typeof panel.id === "number") return pieceColor(panel.id);
  return colours[sizeKey(panel)] || "#d7c4a8";
}

function pieceAttr(panel) {
  if (typeof panel.id !== "number") return "";
  return ' data-piece="' + panel.id + '"';
}

function canonical(job) {
  return JSON.stringify({
    kerf_mm: job.kerf_mm,
    available: job.available.map(function (row) { return [row.count, row.w, row.h]; }),
    desired: job.desired.map(function (row) {
      return [row.count, row.w, row.h, row.grain ? 1 : 0, row.face || "", row.u || 0, row.v || 0, row.name || ""];
    })
  });
}

function fittedText(x, y, w, h, lines, fill) {
  var longest = 1;
  lines.forEach(function (line) {
    if (line.length > longest) longest = line.length;
  });
  var fs = Math.min(
    90,
    Math.floor((w * 0.9) / (longest * 0.62)),
    Math.floor((h * 0.8) / (lines.length * 1.25))
  );
  if (!(fs >= 42)) return "";
  var block = lines.length * fs * 1.15;
  var start = y + (h - block) / 2 + fs * 0.82;
  var out = "";
  lines.forEach(function (line, index) {
    var ty = start + index * fs * 1.15;
    out += '<text x="' + (x + w / 2) + '" y="' + ty.toFixed(1) + '" text-anchor="middle" font-size="' + fs +
      '" fill="' + fill + '" font-family="Palatino, Georgia, serif" stroke="#fffaf3" stroke-width="' +
      Math.max(2, Math.floor(fs / 12)) + '" paint-order="stroke">' + esc(line) + "</text>";
  });
  return out;
}

function boardSvg(sheet, colours) {
  var id = "s" + sheet.index;
  var labelBits = sheet.placements.map(function (panel) {
    return panel.w + " by " + panel.h + " at " + panel.x + "," + panel.y;
  });
  var label = "Sheet " + sheet.index + ", " + sheet.w + " by " + sheet.h + " millimetres. " + labelBits.join(". ");
  var body = "";
  body += '<defs>';
  body += '<pattern id="waste-' + id + '" patternUnits="userSpaceOnUse" width="36" height="36" patternTransform="rotate(45)">';
  body += '<rect width="36" height="36" fill="#f4e7d4"/><line x1="0" y1="0" x2="0" y2="36" stroke="#c4a484" stroke-width="10"/>';
  body += "</pattern>";
  body += '<pattern id="grain-' + id + '" patternUnits="userSpaceOnUse" width="70" height="70">';
  body += '<line x1="8" y1="0" x2="8" y2="70" stroke="#1f1a14" stroke-opacity="0.28" stroke-width="3"/>';
  body += "</pattern></defs>";
  body += '<rect x="0" y="0" width="' + sheet.w + '" height="' + sheet.h + '" fill="url(#waste-' + id + ')"/>';
  sheet.placements.forEach(function (panel) {
    var fill = fillFor(panel, colours);
    var title = (panel.name ? panel.name + ", " : "") + panel.w + " × " + panel.h;
    body += '<g class="panel"' + pieceAttr(panel) + '>';
    body += '<rect x="' + panel.x + '" y="' + panel.y + '" width="' + panel.w + '" height="' + panel.h +
      '" fill="' + fill + '" stroke="#1f1a14" stroke-width="2" vector-effect="non-scaling-stroke"><title>' +
      esc(title) + "</title></rect>";
    if (panel.grain) {
      body += '<rect x="' + panel.x + '" y="' + panel.y + '" width="' + panel.w + '" height="' + panel.h +
        '" fill="url(#grain-' + id + ')"/>';
    }
    var lines = [panel.w + " × " + panel.h];
    if (panel.rotated) lines.push("turned");
    else if (panel.grain) lines.push("locked");
    if (panel.name && panel.w >= 700 && panel.h >= 500) lines.unshift(panel.name);
    body += fittedText(panel.x, panel.y, panel.w, panel.h, lines, "#1f1a14");
    body += "</g>";
  });
  sheet.kerf.forEach(function (band) {
    body += '<rect x="' + band.x + '" y="' + band.y + '" width="' + band.w + '" height="' + band.h +
      '" fill="#1f1a14"><title>' + (band.w < band.h ? band.w : band.h) + " mm kerf</title></rect>";
    var x1;
    var y1;
    var x2;
    var y2;
    if (band.w <= band.h) {
      x1 = band.x + band.w / 2;
      x2 = x1;
      y1 = band.y;
      y2 = band.y + band.h;
    } else {
      y1 = band.y + band.h / 2;
      y2 = y1;
      x1 = band.x;
      x2 = band.x + band.w;
    }
    body += '<line x1="' + x1 + '" y1="' + y1 + '" x2="' + x2 + '" y2="' + y2 +
      '" stroke="#1a120c" stroke-width="4" vector-effect="non-scaling-stroke"/>';
  });
  sheet.waste.forEach(function (offcut) {
    body += fittedText(offcut.x, offcut.y, offcut.w, offcut.h, [offcut.w + " × " + offcut.h, "offcut"], "#6d6256");
  });
  body += '<rect x="0" y="0" width="' + sheet.w + '" height="' + sheet.h +
    '" fill="none" stroke="#1f1a14" stroke-width="3" vector-effect="non-scaling-stroke"/>';
  return '<svg class="board" viewBox="0 0 ' + sheet.w + " " + sheet.h + '" style="aspect-ratio:' + sheet.w + " / " +
    sheet.h + '" role="img" aria-label="' + esc(label) + '">' + body + "</svg>";
}

function chipsHtml(sheet, colours) {
  var html = sheet.placements.map(function (panel, index) {
    var note = panel.rotated ? " turned" : (panel.grain ? " face locked" : "");
    var title = panel.name ? panel.name + " · " : "";
    return "<span class='chip'" + pieceAttr(panel) + "><i style='background:" + fillFor(panel, colours) + "'></i>" +
      (index + 1) + " · " + esc(title) + panel.w + " × " + panel.h + note + "</span>";
  }).join("");
  sheet.waste.forEach(function (offcut) {
    html += "<span class='chip off'>offcut " + offcut.w + " × " + offcut.h + "</span>";
  });
  return "<p class='chips'>" + html + "</p>";
}

function fig(w, maxW, inner) {
  var pct = (100 * w / maxW);
  var wide = pct > 100.05 ? " wide" : "";
  return '<div class="fig' + wide + '" style="width:' + pct.toFixed(4) + '%">' + inner + "</div>";
}

function maxSheetWidth(plan) {
  var maxW = 0;
  plan.sheets.forEach(function (sheet) {
    if (sheet.w > maxW) maxW = sheet.w;
  });
  if (!maxW) {
    plan.unplaced.forEach(function (panel) {
      maxW = Math.max(maxW, panel.w, panel.h);
    });
  }
  return maxW || 1;
}

function legendHtml(plan) {
  return "<li><i class='swatch mix'></i>Each panel keeps one colour on the sheet and in the room</li>" +
    "<li><i class='key off'></i>Offcut</li><li><i class='key kerf'></i>Kerf " + plan.kerf_mm + " mm</li>";
}

function unplacedHtml(plan, colours, maxW) {
  if (!plan.unplaced.length) return "";
  var html = "<div class='length-group unplaced-draw'><h3>Did not fit</h3><p class='note'>Drawn at the same scale as the sheets. Nothing was added to the pull list for these.</p>";
  plan.unplaced.forEach(function (panel) {
    var tried = panel.grain
      ? "Face direction locked, so " + panel.h + " × " + panel.w + " was not tried."
      : (panel.w === panel.h
        ? "Does not fit a stock sheet."
        : "Tried " + panel.w + " × " + panel.h + " and " + panel.h + " × " + panel.w + ". Neither fits a stock sheet.");
    if (panel.w > maxW) {
      tried += " Drawn wider than the widest stock sheet (" + commas(maxW) + " mm).";
    }
    var fake = {
      index: "x",
      w: panel.w,
      h: panel.h,
      placements: [{
        x: 0, y: 0, w: panel.w, h: panel.h, rotated: false, grain: panel.grain,
        source_w: panel.w, source_h: panel.h,
        id: panel.id, face: panel.face, name: panel.name, u: panel.u, v: panel.v
      }],
      kerf: [],
      waste: []
    };
    html += "<article class='board miss-piece'><div class='meta'><span class='idx'>Not placed</span><span class='stock'>" +
      esc(mmSize(panel.w, panel.h)) + "</span></div>" + fig(panel.w, maxW, boardSvg(fake, colours)) +
      "<p class='note'>" + esc(tried) + "</p></article>";
  });
  return html + "</div>";
}

var selectedId = null;
var currentPlan = null;
var roomViewState = {rx: -60, ry: 130, z: 0.082, px: 0, py: 10};
var roomPointers = {};
var roomPinched = false;
var ROOM_CENTER = {x: 1800, y: 1350, z: 1500};

var FACE_GEOM = {
  south: {type: "wall", along: "x", x0: 0, z: 0, y0: 0, nudge: [0, 0, 18]},
  north: {type: "wall", along: "x", x0: 0, z: 3000, y0: 0, nudge: [0, 0, -18]},
  east: {type: "wall", along: "z", x: 3600, z0: 0, y0: 0, nudge: [-18, 0, 0]},
  west: {type: "wall", along: "z", x: 0, z0: 0, y0: 0, nudge: [18, 0, 0]},
  robeFront: {type: "wall", along: "z", x: 600, z0: 600, y0: 0, nudge: [18, 0, 0]},
  robeSouth: {type: "wall", along: "x", x0: 0, z: 600, y0: 0, nudge: [0, 0, -18]},
  robeNorth: {type: "wall", along: "x", x0: 0, z: 1800, y0: 0, nudge: [0, 0, 18]},
  ceiling: {type: "flat", y: 2700, x0: 0, z0: 0, nudge: [0, -18, 0]},
  soffit: {type: "flat", y: 2400, x0: 0, z0: 2500, nudge: [0, -18, 0]},
  bulkhead: {type: "wall", along: "x", x0: 0, z: 2500, y0: 2400, nudge: [0, 0, -18]},
  doorWestJamb: {type: "wall", along: "z", x: 1680, z0: 0, y0: 0, nudge: [8, 0, 0]},
  doorEastJamb: {type: "wall", along: "z", x: 2500, z0: 0, y0: 0, nudge: [-8, 0, 0]},
  doorHead: {type: "flat", y: 2040, x0: 1680, z0: 0, nudge: [0, -8, 0]},
  winLeft: {type: "wall", along: "z", x: 180, z0: 2900, y0: 800, nudge: [8, 0, 0]},
  winRight: {type: "wall", along: "z", x: 1380, z0: 2900, y0: 800, nudge: [-8, 0, 0]},
  winSill: {type: "flat", y: 800, x0: 180, z0: 2900, nudge: [0, 8, 0]},
  winHead: {type: "flat", y: 1900, x0: 180, z0: 2900, nudge: [0, -8, 0]},
  win2Left: {type: "wall", along: "x", x0: 3500, z: 1500, y0: 1100, nudge: [0, 0, -8]},
  win2Right: {type: "wall", along: "x", x0: 3500, z: 2200, y0: 1100, nudge: [0, 0, 8]},
  win2Sill: {type: "flatZ", x: 3600, y: 1100, z0: 1500, nudge: [-6, 6, 0]},
  win2Head: {type: "flatZ", x: 3600, y: 1900, z0: 1500, nudge: [-6, -6, 0]}
};

function cross3(a, b) {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0]
  ];
}

function toCss(x, y, z) {
  return [x - ROOM_CENTER.x, ROOM_CENTER.y - y, z - ROOM_CENTER.z];
}

function panelMatrix(origin, axisU, axisV) {
  var o = toCss(origin[0], origin[1], origin[2]);
  var uEnd = toCss(origin[0] + axisU[0], origin[1] + axisU[1], origin[2] + axisU[2]);
  var vEnd = toCss(origin[0] + axisV[0], origin[1] + axisV[1], origin[2] + axisV[2]);
  var u = [uEnd[0] - o[0], uEnd[1] - o[1], uEnd[2] - o[2]];
  var v = [vEnd[0] - o[0], vEnd[1] - o[1], vEnd[2] - o[2]];
  var n = cross3(u, v);
  return "matrix3d(" + [
    u[0], u[1], u[2], 0,
    v[0], v[1], v[2], 0,
    n[0], n[1], n[2], 0,
    o[0], o[1], o[2], 1
  ].join(",") + ")";
}

function piecePose(face, u, v, w, h) {
  var geom = FACE_GEOM[face];
  if (!geom) return null;
  var nudge = geom.nudge || [0, 0, 0];
  var origin;
  var axisU;
  var axisV;
  if (geom.type === "wall") {
    var top = geom.y0 + v + h;
    if (geom.along === "x") {
      origin = [geom.x0 + u, top, geom.z];
      axisU = [1, 0, 0];
    } else {
      origin = [geom.x, top, geom.z0 + u];
      axisU = [0, 0, 1];
    }
    axisV = [0, -1, 0];
  } else if (geom.type === "flatZ") {
    origin = [geom.x, geom.y, geom.z0 + u];
    axisU = [0, 0, 1];
    axisV = [-1, 0, 0];
  } else {
    origin = [geom.x0 + u, geom.y, geom.z0 + v];
    axisU = [1, 0, 0];
    axisV = [0, 0, 1];
  }
  origin = [origin[0] + nudge[0], origin[1] + nudge[1], origin[2] + nudge[2]];
  return {origin: origin, axisU: axisU, axisV: axisV};
}

function addRoomFace(parent, spec) {
  var pose = piecePose(spec.face, spec.u || 0, spec.v || 0, spec.w, spec.h);
  if (!pose) return;
  var el = document.createElement("div");
  el.className = spec.className;
  el.style.width = spec.w + "px";
  el.style.height = spec.h + "px";
  if (spec.fill) el.style.background = spec.fill;
  if (typeof spec.id === "number") el.setAttribute("data-piece", String(spec.id));
  if (spec.title) el.title = spec.title;
  el.style.transform = panelMatrix(pose.origin, pose.axisU, pose.axisV);
  parent.appendChild(el);
}

function collectRoomPieces(plan) {
  var pieces = [];
  plan.sheets.forEach(function (sheet) {
    sheet.placements.forEach(function (panel) {
      if (!panel.face || typeof panel.id !== "number") return;
      pieces.push({
        id: panel.id,
        face: panel.face,
        name: panel.name,
        u: panel.u,
        v: panel.v,
        w: panel.source_w,
        h: panel.source_h,
        placed: true
      });
    });
  });
  plan.unplaced.forEach(function (panel) {
    if (!panel.face || typeof panel.id !== "number") return;
    pieces.push({
      id: panel.id,
      face: panel.face,
      name: panel.name,
      u: panel.u,
      v: panel.v,
      w: panel.w,
      h: panel.h,
      placed: false
    });
  });
  return pieces;
}

function applyRoomView() {
  var rig = document.getElementById("room-rig");
  if (!rig) return;
  var view = roomViewState;
  rig.style.transform = "translate3d(" + view.px.toFixed(1) + "px," + view.py.toFixed(1) + "px,0) scale(" +
    view.z.toFixed(4) + ") rotateX(" + view.rx.toFixed(2) + "deg) rotateY(" + view.ry.toFixed(2) + "deg)";
}

function renderRoom(plan) {
  var rig = document.getElementById("room-rig");
  if (!rig) return;
  rig.innerHTML = "";
  addRoomFace(rig, {className: "room-floor", face: "ceiling", u: 0, v: 0, w: 3600, h: 3000, fill: "#c4b8a4"});
  var floor = rig.lastChild;
  if (floor) {
    var pose = {
      origin: [0, -8, 0],
      axisU: [1, 0, 0],
      axisV: [0, 0, 1]
    };
    floor.style.transform = panelMatrix(pose.origin, pose.axisU, pose.axisV);
  }
  collectRoomPieces(plan).forEach(function (piece) {
    addRoomFace(rig, {
      className: piece.placed ? "room-panel" : "room-panel loose",
      face: piece.face,
      id: piece.id,
      u: piece.u,
      v: piece.v,
      w: piece.w,
      h: piece.h,
      fill: pieceColor(piece.id),
      title: piece.name
    });
  });
  var room = (typeof SAMPLE !== "undefined" && SAMPLE && SAMPLE.room) ? SAMPLE.room : null;
  if (room && room.openings) {
    room.openings.forEach(function (opening) {
      var geom = FACE_GEOM[opening.face];
      var pose = piecePose(opening.face, opening.u, opening.v, opening.w, opening.h);
      if (!pose || !geom || !geom.nudge) return;
      var origin = pose.origin.slice();
      origin[0] -= geom.nudge[0] * 4;
      origin[1] -= geom.nudge[1] * 4;
      origin[2] -= geom.nudge[2] * 4;
      var hole = document.createElement("div");
      hole.className = "room-opening";
      hole.style.width = opening.w + "px";
      hole.style.height = opening.h + "px";
      hole.title = opening.name || "Opening";
      hole.style.transform = panelMatrix(origin, pose.axisU, pose.axisV);
      rig.appendChild(hole);
    });
  }
  applyRoomView();
}

function findPiece(plan, id) {
  var found = null;
  function scan(panel) {
    if (typeof panel.id === "number" && String(panel.id) === String(id)) found = panel;
  }
  if (!plan) return null;
  plan.sheets.forEach(function (sheet) { sheet.placements.forEach(scan); });
  plan.unplaced.forEach(scan);
  return found;
}

function applySelection(plan) {
  var nodes = document.querySelectorAll("[data-piece]");
  nodes.forEach(function (el) {
    var on = selectedId !== null && el.getAttribute("data-piece") === String(selectedId);
    el.classList.toggle("on", on);
    el.classList.toggle("dim", selectedId !== null && !on);
  });
  var info = document.getElementById("piece-info");
  if (!info) return;
  if (selectedId === null) {
    info.textContent = "Tap a coloured panel. The same colour is on the sheet and in the room.";
    return;
  }
  var piece = findPiece(plan, selectedId);
  if (!piece) {
    selectedId = null;
    info.textContent = "Tap a coloured panel. The same colour is on the sheet and in the room.";
    nodes.forEach(function (el) { el.classList.remove("on"); el.classList.remove("dim"); });
    return;
  }
  var w = piece.source_w || piece.w;
  var h = piece.source_h || piece.h;
  var missing = plan.unplaced.some(function (panel) { return String(panel.id) === String(selectedId); });
  info.textContent = (piece.name || "Panel") + " · " + w + " × " + h + " mm" + (missing ? " · not on a sheet" : "");
}

function selectPiece(id, plan) {
  if (id === null || id === undefined || id === "") return;
  selectedId = String(selectedId) === String(id) ? null : id;
  applySelection(plan);
}

function paint(job) {
  var plan = packJob(job);
  var error = document.getElementById("error");
  if (plan.error) {
    if (error) {
      error.hidden = false;
      error.textContent = plan.error;
    }
    ["pull-list", "pull-total", "leave-block", "missing-block", "cut-body", "cut-legend"].forEach(function (id) {
      var node = document.getElementById(id);
      if (node) node.innerHTML = "";
    });
    var rig = document.getElementById("room-rig");
    if (rig) rig.innerHTML = "";
    currentPlan = null;
    var pre = document.getElementById("lumber-text");
    if (pre) pre.textContent = plan.error;
    return;
  }
  if (error) error.hidden = true;

  var mode = "plain";
  if (typeof SAMPLE !== "undefined" && SAMPLE && canonical(job) === canonical(SAMPLE)) {
    mode = SAMPLE.example ? "example" : "plain";
  } else if (typeof SAMPLE !== "undefined" && SAMPLE) {
    mode = "custom";
  } else if (job.example) {
    mode = "example";
  }
  var kicker = document.getElementById("kicker");
  var banner = document.getElementById("banner");
  var fictional = mode === "example" && SAMPLE && SAMPLE.fictional;
  var story = document.getElementById("story");
  if (story && SAMPLE && SAMPLE.story) story.textContent = SAMPLE.story;
  if (kicker) {
    kicker.textContent = mode === "custom"
      ? "Edited on this phone"
      : (fictional ? "Example · fictional" : (mode === "example" ? "Example · synthetic job" : "Plasterboard"));
  }
  if (banner) {
    if (mode === "custom") {
      banner.textContent = "Edited on this phone. Still not a real job. Restore example job reloads the fictional spare room.";
    } else if (fictional) {
      banner.textContent = "EXAMPLE / FICTIONAL — not a real job. This spare room is made up.";
    } else if (mode === "example") {
      banner.textContent = "EXAMPLE / SYNTHETIC — not a real job. The counts and sizes shipped with this page are made up.";
    } else {
      banner.textContent = "Plasterboard cut plan.";
    }
  }

  var pulls = sheetGroups(plan.sheets, true);
  var leaves = sheetGroups(plan.sheets, false);
  var placedN = 0;
  plan.sheets.forEach(function (sheet) { placedN += sheet.placements.length; });
  var pullN = pulls.reduce(function (sum, group) { return sum + group.n; }, 0);
  var leaveN = leaves.reduce(function (sum, group) { return sum + group.n; }, 0);
  var stats = document.getElementById("stats");
  if (stats) {
    stats.innerHTML =
      "<div><dt>Pull</dt><dd>" + countLabel(pullN, "sheet", "sheets") + "</dd></div>" +
      "<div><dt>Leave</dt><dd>" + countLabel(leaveN, "sheet", "sheets") + "</dd></div>" +
      "<div class='ok'><dt>Placed</dt><dd>" + countLabel(placedN, "panel", "panels") + "</dd></div>" +
      "<div class='" + (plan.unplaced.length ? "bad" : "ok") + "'><dt>Not placed</dt><dd>" +
      countLabel(plan.unplaced.length, "panel", "panels") + "</dd></div>";
  }
  var summary = document.getElementById("summary-note");
  if (summary) {
    var pullArea = 0;
    pulls.forEach(function (group) { pullArea += group.n * group.w * group.h; });
    summary.textContent = "Saw kerf " + job.kerf_mm + " mm. Pull " + areaLabel(pullArea) +
      ". Packing is guillotine best-area fit with a shorter-leftover split, not an exact optimum.";
  }

  var pullHtml = pulls.map(function (group) {
    return "<li><label><input type='checkbox'><span class='count'>" + group.n +
      "</span><span class='mm'>" + esc(mmSize(group.w, group.h)) + "</span><span class='m'>" +
      esc(areaLabel(group.w * group.h)) + " each</span></label></li>";
  }).join("");
  if (!pullHtml) pullHtml = "<li><p class='note'>No sheet is cut in this plan.</p></li>";
  var pullList = document.getElementById("pull-list");
  if (pullList) pullList.innerHTML = pullHtml;
  var pullTotal = document.getElementById("pull-total");
  if (pullTotal) {
    var totalArea = 0;
    pulls.forEach(function (group) { totalArea += group.n * group.w * group.h; });
    pullTotal.textContent = pullN ? (pullN + " sheets · " + areaLabel(totalArea)) : "";
  }

  var leaveBlock = document.getElementById("leave-block");
  if (leaveBlock) {
    if (leaves.length) {
      var leaveItems = leaves.map(function (group) {
        return "<li><span class='count'>" + group.n + "</span><span class='mm'>" + esc(mmSize(group.w, group.h)) +
          "</span><span class='m'>" + esc(areaLabel(group.w * group.h)) + " each</span></li>";
      }).join("");
      leaveBlock.innerHTML = "<h3>Leave on the rack</h3><ul class='leave'>" + leaveItems + "</ul>";
    } else {
      leaveBlock.innerHTML = "<h3>Leave on the rack</h3><p class='note'>Every available sheet is cut in this plan.</p>";
    }
  }

  var missingBlock = document.getElementById("missing-block");
  if (missingBlock) {
    if (plan.unplaced.length) {
      var bits = panelGroups(plan.unplaced).map(function (group) {
        var lock = group.grain ? "face locked" : "turns allowed";
        return group.n + " × " + mmSize(group.w, group.h) + " (" + lock + ")";
      }).join(", ");
      missingBlock.innerHTML = "<h3>Panels that did not fit</h3><p>" + esc(bits) +
        "</p><p class='note'>These sizes are from the panel list. This page does not choose a sheet to buy. The drawing is with the cut plan, at the same scale.</p>";
    } else {
      missingBlock.innerHTML = "<p class='note'>Every panel is on a sheet in the cut plan.</p>";
    }
  }

  var colours = colourMap(plan);
  var legend = document.getElementById("cut-legend");
  if (legend) legend.innerHTML = legendHtml(plan);
  var cutNote = document.getElementById("cut-note");
  if (cutNote) {
    cutNote.textContent = "Skinny panels are the sills, lintels, and side fills that stop at the door and the two windows. Each sheet is to scale with the others. A panel's colour is the same on the sheet and in the room. Tap one to mark it in both. Hatched areas are offcuts. The dark strip is the " +
      job.kerf_mm + " mm saw kerf, drawn with a hairline so a thin blade still shows. A panel marked turned was rotated 90°. Locked panels keep the width and height you entered. Sheet numbers follow the stock list after counts are expanded. A number that is missing here was left on the rack.";
  }

  var maxW = maxSheetWidth(plan);
  var html = "";
  var previous = "";
  plan.sheets.forEach(function (sheet) {
    if (!sheet.used) return;
    var key = sheet.w + "x" + sheet.h;
    if (key !== previous) {
      if (previous) html += "</div>";
      html += "<div class='length-group'><h3>" + esc(mmSize(sheet.w, sheet.h)) + "</h3>";
      previous = key;
    }
    var wasteArea = 0;
    sheet.waste.forEach(function (offcut) { wasteArea += offcut.w * offcut.h; });
    html += "<article class='board'><div class='meta'><span class='idx'>Sheet " + sheet.index +
      "</span><span class='stock'>" + esc(mmSize(sheet.w, sheet.h)) + "</span><span class='cuts-n'>" +
      sheet.placements.length + " panels · offcut " + esc(areaLabel(wasteArea)) + "</span></div>" +
      fig(sheet.w, maxW, boardSvg(sheet, colours)) + chipsHtml(sheet, colours) +
      "<p class='check'>" + esc(equation(sheet)) + "</p></article>";
  });
  if (previous) html += "</div>";
  if (!plan.sheets.length) html += "<p class='note'>No stock sheets.</p>";
  html += unplacedHtml(plan, colours, maxW);
  var cutBody = document.getElementById("cut-body");
  if (cutBody) cutBody.innerHTML = html;
  currentPlan = plan;
  renderRoom(plan);
  applySelection(plan);

  var pre = document.getElementById("lumber-text");
  if (pre) {
    var textJob = mode === "example" && SAMPLE ? SAMPLE : job;
    pre.textContent = shopText(plan, textJob, mode === "custom");
  }
  var editNote = document.getElementById("edit-note");
  if (editNote) {
    var stockN = job.available.reduce(function (sum, row) { return sum + row.count; }, 0);
    var pieceN = job.desired.reduce(function (sum, row) { return sum + row.count; }, 0);
    editNote.textContent = job.available.length + " stock rows, " + stockN + " sheets on hand. " +
      job.desired.length + " panel rows, " + pieceN + " panels. Width runs across the sheet. Height runs down the drawing. A locked panel is not turned.";
  }
}

function rowFields(kind, row) {
  var count = row ? row.count : "";
  var width = row ? row.w : "";
  var height = row ? row.h : "";
  var lock = "";
  var meta = "";
  var nameLine = "";
  if (kind === "panel") {
    lock = '<label class="lock"><input type="checkbox"' + (row && row.grain ? " checked" : "") +
      "> Face direction locked</label>";
    if (row && row.face) {
      meta = ' data-face="' + esc(row.face) + '" data-name="' + esc(row.name || row.face) +
        '" data-u="' + row.u + '" data-v="' + row.v + '"';
    }
    if (row && row.name) nameLine = '<p class="piece-name">' + esc(row.name) + "</p>";
  }
  return '<div class="edit-row"' + meta + '><label>Count <input inputmode="numeric" enterkeyhint="done" autocomplete="off" min="1" step="1" value="' +
    count + '"></label><label>Width mm <input inputmode="numeric" enterkeyhint="done" autocomplete="off" min="1" step="1" value="' +
    width + '"></label><label>Height mm <input inputmode="numeric" enterkeyhint="done" autocomplete="off" min="1" step="1" value="' +
    height + '"></label><button type="button" class="remove ghost">Remove</button>' + nameLine + lock + "</div>";
}

function fillForm(job) {
  document.getElementById("stock-rows").innerHTML = job.available.map(function (row) {
    return rowFields("stock", row);
  }).join("");
  document.getElementById("panel-rows").innerHTML = job.desired.map(function (row) {
    return rowFields("panel", row);
  }).join("");
  document.getElementById("kerf-input").value = String(job.kerf_mm);
}

function readRows(container, withGrain) {
  var rows = [];
  container.querySelectorAll(".edit-row").forEach(function (row) {
    var inputs = row.querySelectorAll("input");
    var count = parseInt(inputs[0].value, 10);
    var width = parseInt(inputs[1].value, 10);
    var height = parseInt(inputs[2].value, 10);
    if (!(count > 0 && width > 0 && height > 0)) return;
    var item = {count: count, w: width, h: height};
    if (withGrain) item.grain = !!(inputs[3] && inputs[3].checked);
    var face = row.getAttribute("data-face");
    if (face) {
      item.face = face;
      item.name = row.getAttribute("data-name") || face;
      item.u = parseInt(row.getAttribute("data-u"), 10) || 0;
      item.v = parseInt(row.getAttribute("data-v"), 10) || 0;
    }
    rows.push(item);
  });
  return rows;
}

function readJob() {
  var kerf = parseInt(document.getElementById("kerf-input").value, 10);
  if (!(kerf >= 0)) return null;
  return {
    kerf_mm: kerf,
    example: false,
    available: readRows(document.getElementById("stock-rows"), false),
    desired: readRows(document.getElementById("panel-rows"), true)
  };
}

function validJob(job) {
  if (!job || typeof job.kerf_mm !== "number" || job.kerf_mm < 0) return false;
  if (!Array.isArray(job.available) || !Array.isArray(job.desired)) return false;
  return job.available.concat(job.desired).every(function (row) {
    return row && row.count > 0 && row.w > 0 && row.h > 0;
  });
}

function boot() {
  var edit = document.getElementById("edit");
  if (!edit || !SAMPLE) return;
  var timer = 0;
  function apply() {
    var job = readJob();
    if (!job) return;
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(job)); } catch (err) { /* private mode */ }
    paint(job);
  }
  var editLink = document.querySelector('a[href="#edit"]');
  if (editLink) editLink.addEventListener("click", function () { edit.open = true; });
  if (location.hash === "#edit") edit.open = true;
  edit.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(apply, 150);
  });
  edit.addEventListener("click", function (event) {
    var button = event.target.closest("button");
    if (!button || !button.classList.contains("remove")) return;
    var row = button.closest(".edit-row");
    if (row) row.remove();
    apply();
  });
  document.getElementById("add-stock").addEventListener("click", function () {
    var box = document.getElementById("stock-rows");
    box.insertAdjacentHTML("beforeend", rowFields("stock", null));
    var field = box.querySelector(".edit-row:last-child input");
    if (field) field.focus();
  });
  document.getElementById("add-panel").addEventListener("click", function () {
    var box = document.getElementById("panel-rows");
    box.insertAdjacentHTML("beforeend", rowFields("panel", null));
    var field = box.querySelector(".edit-row:last-child input");
    if (field) field.focus();
  });
  document.getElementById("restore-sample").addEventListener("click", function () {
    try { localStorage.removeItem(STORAGE_KEY); } catch (err) { /* private mode */ }
    selectedId = null;
    fillForm(SAMPLE);
    paint(SAMPLE);
  });
  var cutBody = document.getElementById("cut-body");
  if (cutBody) {
    cutBody.addEventListener("click", function (event) {
      var el = event.target.closest("[data-piece]");
      if (!el) return;
      selectPiece(el.getAttribute("data-piece"), currentPlan);
    });
  }
  var roomView = document.getElementById("room-view");
  var resetBtn = document.getElementById("room-reset");
  if (resetBtn) {
    resetBtn.addEventListener("click", function () {
      roomViewState = {rx: -60, ry: 130, z: 0.082, px: 0, py: 10};
      applyRoomView();
    });
  }
  if (roomView) {
    roomView.addEventListener("pointerdown", function (event) {
      try { roomView.setPointerCapture(event.pointerId); } catch (err) { /* already gone */ }
      roomPointers[event.pointerId] = {x: event.clientX, y: event.clientY, sx: event.clientX, sy: event.clientY};
    });
    roomView.addEventListener("pointermove", function (event) {
      var point = roomPointers[event.pointerId];
      if (!point) return;
      var ids = Object.keys(roomPointers);
      var prevX = point.x;
      var prevY = point.y;
      point.x = event.clientX;
      point.y = event.clientY;
      if (ids.length >= 2) {
        roomPinched = true;
        var a = roomPointers[ids[0]];
        var b = roomPointers[ids[1]];
        var dist = Math.hypot(b.x - a.x, b.y - a.y) || 1;
        var mx = (a.x + b.x) / 2;
        var my = (a.y + b.y) / 2;
        if (!roomView._pinch) {
          roomView._pinch = {dist: dist, mx: mx, my: my, z: roomViewState.z, px: roomViewState.px, py: roomViewState.py};
        }
        var base = roomView._pinch;
        var nextZ = base.z * (dist / base.dist);
        if (nextZ < 0.03) nextZ = 0.03;
        if (nextZ > 0.16) nextZ = 0.16;
        roomViewState.z = nextZ;
        roomViewState.px = base.px + (mx - base.mx);
        roomViewState.py = base.py + (my - base.my);
        applyRoomView();
        return;
      }
      var dx = event.clientX - prevX;
      var dy = event.clientY - prevY;
      roomViewState.ry += dx * 0.35;
      roomViewState.rx += dy * 0.28;
      if (roomViewState.rx > 80) roomViewState.rx = 80;
      if (roomViewState.rx < -80) roomViewState.rx = -80;
      applyRoomView();
    });
    function endRoomPointer(event) {
      var point = roomPointers[event.pointerId];
      delete roomPointers[event.pointerId];
      if (Object.keys(roomPointers).length < 2) roomView._pinch = null;
      if (!point) return;
      var moved = Math.hypot(event.clientX - point.sx, event.clientY - point.sy);
      if (moved < 6 && !roomPinched && Object.keys(roomPointers).length === 0) {
        var el = document.elementFromPoint(event.clientX, event.clientY);
        var piece = el && el.closest ? el.closest("[data-piece]") : null;
        if (piece && roomView.contains(piece)) selectPiece(piece.getAttribute("data-piece"), currentPlan);
      }
      if (Object.keys(roomPointers).length === 0) roomPinched = false;
    }
    roomView.addEventListener("pointerup", endRoomPointer);
    roomView.addEventListener("pointercancel", endRoomPointer);
    roomView.addEventListener("wheel", function (event) {
      event.preventDefault();
      var factor = event.deltaY > 0 ? 0.92 : 1.08;
      var nextZ = roomViewState.z * factor;
      if (nextZ < 0.03) nextZ = 0.03;
      if (nextZ > 0.16) nextZ = 0.16;
      roomViewState.z = nextZ;
      applyRoomView();
    }, {passive: false});
  }
  var saved = null;
  try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"); } catch (err) { saved = null; }
  if (validJob(saved)) {
    fillForm(saved);
    paint(saved);
  } else {
    fillForm(SAMPLE);
    paint(SAMPLE);
  }
}

if (typeof document !== "undefined") boot();
