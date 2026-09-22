/* Offline editor for the shop sheet. Pure functions stay above the DOM boot
   so tests can run them without a browser. The sample job is substituted
   when the page is generated. */
var SAMPLE = __SAMPLE_JOB__;
var STORAGE_KEY = "planker-edit-v1";
var CUT_COLOURS = [
  "#8c2f1b", "#d85a1a", "#c48a00", "#5f7f24", "#1f7a4d", "#0f766e",
  "#1d6a93", "#2a4e8a", "#5b3f8c", "#8e3a78", "#a33b4a", "#6b4a2a",
  "#3e4c59", "#b45309", "#3f6212", "#57534e"
];

function expandRows(rows) {
  var out = [];
  rows.forEach(function (row) {
    var count = row[0];
    var length = row[1];
    for (var i = 0; i < count; i++) out.push(length);
  });
  return out;
}

function allocateGreedy(pieces, cuts, kerf) {
  var allocated = pieces.map(function () { return []; });
  var unallocated = [];
  var leftover = pieces.map(function (length) { return length + kerf; });
  cuts.forEach(function (want) {
    var need = want + kerf;
    var bestI = -1;
    var bestRemain = Infinity;
    for (var i = 0; i < leftover.length; i++) {
      var remain = leftover[i];
      if (remain >= need && remain < bestRemain) {
        bestRemain = remain;
        bestI = i;
      }
    }
    if (bestI >= 0) {
      allocated[bestI].push(want);
      leftover[bestI] -= need;
    } else {
      unallocated.push(want);
    }
  });
  return { allocated: allocated, unallocated: unallocated, leftover: leftover };
}

function buildPlan(job) {
  var stocks = expandRows(job.available);
  var desired = expandRows(job.desired).slice().sort(function (a, b) { return b - a; });
  var cut = allocateGreedy(stocks, desired, job.kerf);
  var boards = stocks.map(function (stock, index) {
    return {
      index: index + 1,
      stock: stock,
      cuts: cut.allocated[index],
      leftover: cut.leftover[index]
    };
  });
  return { boards: boards, unallocated: cut.unallocated, desired: desired };
}

function countsOf(lengths) {
  var map = new Map();
  lengths.forEach(function (length) {
    map.set(length, (map.get(length) || 0) + 1);
  });
  return Array.from(map.entries()).sort(function (a, b) { return b[0] - a[0]; });
}

function metres(mm) {
  var sign = mm < 0 ? "-" : "";
  var abs = Math.abs(mm);
  var whole = Math.floor(abs / 1000);
  var frac = abs % 1000;
  return sign + whole + "." + String(frac).padStart(3, "0") + " m";
}

function mmText(mm) {
  return mm.toLocaleString("en-US") + " mm";
}

function esc(value) {
  return String(value).replace(/[&<>"']/g, function (ch) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
  });
}

function colourMap(lengths) {
  var unique = Array.from(new Set(lengths)).sort(function (a, b) { return b - a; });
  var map = {};
  unique.forEach(function (length, index) {
    map[length] = CUT_COLOURS[index % CUT_COLOURS.length];
  });
  return map;
}

function offcutPhrase(leftover, pieceLengths) {
  var lengths = Array.from(new Set(pieceLengths)).sort(function (a, b) { return a - b; });
  if (leftover <= 0 || !lengths.length) return "no offcut";
  var fits = lengths.filter(function (length) { return length <= leftover; });
  var longer = lengths.filter(function (length) { return length > leftover; });
  if (!fits.length) {
    return "too short for a " + lengths[0].toLocaleString("en-US") + " mm piece, the shortest on this job";
  }
  var longestFit = fits[fits.length - 1];
  if (longer.length) {
    return "long enough for " + longestFit.toLocaleString("en-US") + " mm, shorter than " + longer[0].toLocaleString("en-US") + " mm";
  }
  return "long enough for " + longestFit.toLocaleString("en-US") + " mm, the longest piece on this job";
}

function lumberLines(job, plan) {
  var lines = [
    "PLANKER LUMBER LIST",
    "Kerf: " + job.kerf + " mm between cuts on the same board",
    "",
    "PULL"
  ];
  var used = plan.boards.filter(function (board) { return board.cuts.length; });
  var pulls = countsOf(used.map(function (board) { return board.stock; }));
  if (pulls.length) {
    pulls.forEach(function (pair) {
      lines.push(pair[1] + " x " + pair[0] + " mm (" + metres(pair[0]) + ")");
    });
    var totalMm = used.reduce(function (sum, board) { return sum + board.stock; }, 0);
    var totalN = pulls.reduce(function (sum, pair) { return sum + pair[1]; }, 0);
    lines.push("Total: " + totalN + " boards, " + totalMm + " mm (" + metres(totalMm) + ")");
  } else {
    lines.push("none");
  }
  lines.push("", "LEAVE");
  var leaves = countsOf(plan.boards.filter(function (board) { return !board.cuts.length; }).map(function (board) { return board.stock; }));
  if (leaves.length) {
    leaves.forEach(function (pair) {
      lines.push(pair[1] + " x " + pair[0] + " mm (" + metres(pair[0]) + ")");
    });
  } else {
    lines.push("none");
  }
  lines.push("", "DOES NOT FIT");
  var missing = countsOf(plan.unallocated);
  if (missing.length) {
    missing.forEach(function (pair) {
      lines.push(pair[1] + " x " + pair[0] + " mm");
    });
    lines.push("These are piece lengths from desired, not a board to order.");
  } else {
    lines.push("none");
  }
  lines.push("");
  return lines.join("\n");
}

function rulerHtml(maxMm) {
  if (!maxMm) return "";
  var labels = [0];
  var tick;
  for (tick = 1000; tick < maxMm; tick += 1000) {
    if (maxMm - tick >= 800) labels.push(tick);
  }
  if (labels[labels.length - 1] !== maxMm) labels.push(maxMm);
  var seen = {};
  var ticks = "";
  var list = [];
  for (tick = 0; tick <= maxMm; tick += 500) list.push(tick);
  list.push(maxMm);
  list.forEach(function (mark) {
    if (seen[mark] || mark > maxMm) return;
    seen[mark] = true;
    var major = mark % 1000 === 0 || mark === maxMm;
    var pct = (100 * mark / maxMm).toFixed(4);
    ticks += '<i class="' + (major ? "major" : "minor") + '" style="left:' + pct + '%"></i>';
  });
  var marks = labels.map(function (mark) {
    var pct = (100 * mark / maxMm).toFixed(4);
    var cls = mark === 0 ? "start" : mark === maxMm ? "end" : "mid";
    return '<span class="' + cls + '" style="left:' + pct + '%">' + mark + "</span>";
  }).join("");
  return '<div class="board ruler-row"><div class="meta"></div><div class="viz"><div class="ruler" aria-hidden="true">' + ticks + marks + "</div></div><div></div></div>";
}

function barSvg(board, kerf, colours, maxMm) {
  var top = 12;
  var barH = 420;
  var height = top + barH + 28;
  var x = 0;
  var body = "";
  var defs =
    '<pattern id="offcut-' + board.index + '" patternUnits="userSpaceOnUse" width="90" height="90" patternTransform="rotate(45)">' +
    '<rect width="90" height="90" fill="#f4e7d4"/><line x1="0" y1="0" x2="0" y2="90" stroke="#c4a484" stroke-width="28"/></pattern>' +
    '<pattern id="unused-' + board.index + '" patternUnits="userSpaceOnUse" width="120" height="120" patternTransform="rotate(45)">' +
    '<rect width="120" height="120" fill="#f7f1e6"/><line x1="0" y1="0" x2="0" y2="120" stroke="#d9cbb8" stroke-width="22"/></pattern>';
  if (!board.cuts.length) {
    body += '<rect x="0" y="' + top + '" width="' + board.stock + '" height="' + barH + '" fill="url(#unused-' + board.index + ')"><title>not cut, ' + board.stock + " mm</title></rect>";
  } else {
    board.cuts.forEach(function (cut, index) {
      var colour = colours[cut] || "#57534e";
      body += '<rect x="' + x + '" y="' + top + '" width="' + cut + '" height="' + barH + '" fill="' + colour + '"><title>' + cut + " mm</title></rect>";
      x += cut;
      if (index !== board.cuts.length - 1) {
        body += '<rect x="' + x + '" y="' + top + '" width="' + kerf + '" height="' + barH + '" fill="#1f1a14"><title>' + kerf + " mm kerf</title></rect>";
        var mid = x + kerf / 2;
        body += '<line x1="' + mid + '" y1="' + top + '" x2="' + mid + '" y2="' + (top + barH) + '" stroke="#1a120c" stroke-width="2" vector-effect="non-scaling-stroke"/>';
        x += kerf;
      }
    });
    var left = board.stock - x;
    if (left > 0) {
      body += '<rect x="' + x + '" y="' + top + '" width="' + left + '" height="' + barH + '" fill="url(#offcut-' + board.index + ')"><title>' + left + " mm offcut</title></rect>";
    }
  }
  body += '<rect x="0" y="' + top + '" width="' + board.stock + '" height="' + barH + '" fill="none" stroke="#1f1a14" stroke-width="1.5" vector-effect="non-scaling-stroke"/>';
  var label = board.cuts.length
    ? "Board " + board.index + ", " + board.stock + " mm, cuts " + board.cuts.join(", ") + ", offcut " + board.leftover + " mm"
    : "Board " + board.index + ", " + board.stock + " mm, not cut";
  return '<svg class="bar" viewBox="0 0 ' + maxMm + " " + height + '" preserveAspectRatio="none" role="img" aria-label="' + esc(label) + '"><defs>' + defs + "</defs>" +
    '<line x1="0" y1="' + (top + barH + 16) + '" x2="' + maxMm + '" y2="' + (top + barH + 16) + '" stroke="#e4d9c8" stroke-width="8"/>' +
    body + "</svg>";
}

function checkLine(board, kerf) {
  if (!board.cuts.length) {
    return "not cut — " + mmText(board.stock) + " left whole (spreadsheet leftover " + mmText(board.leftover) + ")";
  }
  var parts = board.cuts.map(function (cut) { return cut.toLocaleString("en-US"); });
  var spans = Math.max(0, board.cuts.length - 1);
  if (spans) parts.push("kerf " + (kerf * spans).toLocaleString("en-US"));
  var left = board.leftover;
  parts.push("offcut " + left.toLocaleString("en-US"));
  return parts.join(" + ") + " = " + board.stock.toLocaleString("en-US");
}

function chipsHtml(board, colours) {
  if (!board.cuts.length) return "<p class='chips'><span class='chip quiet'>no cuts</span></p>";
  var html = board.cuts.map(function (cut) {
    return "<span class='chip'><i style='background:" + (colours[cut] || "#57534e") + "'></i>" + cut + "</span>";
  }).join("");
  if (board.leftover) html += "<span class='chip off'>" + board.leftover + " left</span>";
  return "<p class='chips'>" + html + "</p>";
}

function paint(job) {
  var plan = buildPlan(job);
  var colours = colourMap(plan.desired);
  var used = plan.boards.filter(function (board) { return board.cuts.length; });
  var unused = plan.boards.filter(function (board) { return !board.cuts.length; });
  var pulls = countsOf(used.map(function (board) { return board.stock; }));
  var leaves = countsOf(unused.map(function (board) { return board.stock; }));
  var missing = countsOf(plan.unallocated);
  var onHand = countsOf(plan.boards.map(function (board) { return board.stock; }));
  var pullMap = new Map(pulls);
  var leaveMap = new Map(leaves);
  var placedN = used.reduce(function (sum, board) { return sum + board.cuts.length; }, 0);
  var offcutMm = used.reduce(function (sum, board) { return sum + board.leftover; }, 0);
  var kerfTotal = plan.boards.reduce(function (sum, board) {
    return sum + job.kerf * Math.max(0, board.cuts.length - 1);
  }, 0);
  var onHandMm = plan.boards.reduce(function (sum, board) { return sum + board.stock; }, 0);
  var desiredMm = plan.desired.reduce(function (sum, length) { return sum + length; }, 0);
  var missingN = plan.unallocated.length;
  var pullN = pulls.reduce(function (sum, pair) { return sum + pair[1]; }, 0);
  var leaveN = leaves.reduce(function (sum, pair) { return sum + pair[1]; }, 0);

  var stats = document.getElementById("stats");
  if (stats) {
    stats.innerHTML =
      "<div><dt>Pull</dt><dd>" + pullN + " <small>boards</small></dd></div>" +
      "<div><dt>Leave</dt><dd>" + leaveN + " <small>boards</small></dd></div>" +
      "<div><dt>Placed</dt><dd>" + placedN + " <small>pieces</small></dd></div>" +
      "<div class='" + (missingN ? "bad" : "ok") + "'><dt>Not placed</dt><dd>" + missingN + " <small>pieces</small></dd></div>";
  }
  var summary = document.getElementById("summary-note");
  if (summary) {
    summary.textContent =
      "On hand: " + plan.boards.length + " boards, " + mmText(onHandMm) + " (" + metres(onHandMm) + "). " +
      "Project: " + plan.desired.length + " pieces, " + mmText(desiredMm) + " (" + metres(desiredMm) + "). " +
      "Offcut on pulled boards: " + mmText(offcutMm) + ". Saw kerf: " + mmText(kerfTotal) + ".";
  }

  var pullHtml = pulls.map(function (pair) {
    return "<li><label><input type='checkbox'><span class='count'>" + pair[1] +
      "</span><span class='mm'>" + esc(mmText(pair[0])) + "</span><span class='m'>" +
      esc(metres(pair[0])) + " each</span></label></li>";
  }).join("");
  if (!pullHtml) pullHtml = "<li><p class='note'>No board is long enough for a cut.</p></li>";
  var pullList = document.getElementById("pull-list");
  if (pullList) pullList.innerHTML = pullHtml;
  var pullTotal = document.getElementById("pull-total");
  if (pullTotal) {
    var pullMm = used.reduce(function (sum, board) { return sum + board.stock; }, 0);
    pullTotal.textContent = pullN ? (pullN + " boards · " + mmText(pullMm) + " · " + metres(pullMm)) : "";
  }

  var leaveBlock = document.getElementById("leave-block");
  if (leaveBlock) {
    if (leaves.length) {
      var leaveItems = leaves.map(function (pair) {
        return "<li><span class='count'>" + pair[1] + "</span><span class='mm'>" + esc(mmText(pair[0])) +
          "</span><span class='m'>" + esc(metres(pair[0])) + " each</span></li>";
      }).join("");
      var leaveMm = unused.reduce(function (sum, board) { return sum + board.stock; }, 0);
      leaveBlock.innerHTML = "<h3>Leave on the rack</h3><ul class='leave'>" + leaveItems +
        "</ul><p class='total'>" + leaveN + " boards · " + esc(mmText(leaveMm)) + " · " + esc(metres(leaveMm)) + "</p>";
    } else {
      leaveBlock.innerHTML = "<h3>Leave on the rack</h3><p class='note'>Every available board is cut in this plan.</p>";
    }
  }

  var missingBlock = document.getElementById("missing-block");
  if (missingBlock) {
    if (missing.length) {
      var bits = missing.map(function (pair) { return pair[1] + " × " + mmText(pair[0]); }).join(", ");
      missingBlock.innerHTML = "<h3>Pieces that still need a board</h3><p>" + esc(bits) +
        "</p><p class='note'>These lengths are the pieces from <code>desired</code> that did not fit. This page does not choose a board to buy.</p>";
    } else {
      missingBlock.innerHTML = "<p class='note'>Every desired piece is on a board in the cut plan. Nothing further to buy for these cuts.</p>";
    }
  }

  var balance = document.getElementById("balance-list");
  if (balance) {
    balance.innerHTML = onHand.map(function (pair) {
      var length = pair[0];
      return "<li><span class='mm'>" + esc(mmText(length)) + "</span><span class='sub'>On hand " +
        pair[1] + " · Pull " + (pullMap.get(length) || 0) + " · Leave " + (leaveMap.get(length) || 0) + "</span></li>";
    }).join("") || "<li><span class='mm'>No available boards.</span></li>";
  }

  var pre = document.getElementById("lumber-text");
  if (pre) pre.textContent = lumberLines(job, plan);

  var cutNote = document.getElementById("cut-note");
  if (cutNote) {
    cutNote.textContent = "Each bar is one board, to scale with the ruler (millimetres). Board numbers follow the TSV rows. Left to right is the cut order. A short offcut is a thin sliver; the number at the right is its length. The dark line is the " + job.kerf + " mm kerf, drawn at least a hairline so it stays visible. “Too short” means the offcut is shorter than every piece on this job.";
  }
  var editNote = document.getElementById("edit-note");
  if (editNote) {
    var stockN = job.available.reduce(function (sum, row) { return sum + row[0]; }, 0);
    var pieceN = job.desired.reduce(function (sum, row) { return sum + row[0]; }, 0);
    editNote.textContent =
      job.available.length + " rows, " + stockN + " boards on hand. " +
      job.desired.length + " rows, " + pieceN + " pieces to cut. " +
      "Change a count or a length and the list updates. Add a row only when you have a real length to enter.";
  }
  var legend = document.getElementById("cut-legend");
  if (legend) {
    legend.innerHTML = "<li><i class='key kerf'></i> Kerf " + job.kerf + " mm</li><li><i class='key off'></i> Offcut</li><li><i class='key idle'></i> Board not cut</li>";
  }

  var maxMm = plan.boards.reduce(function (max, board) { return Math.max(max, board.stock); }, 0);
  var html = rulerHtml(maxMm);
  var previous = null;
  plan.boards.forEach(function (board) {
    if (board.stock !== previous) {
      if (previous !== null) html += "</div>";
      html += "<div class='length-group'><h3>" + esc(mmText(board.stock)) + " boards</h3>";
      previous = board.stock;
    }
    var phrase = "";
    var offHtml;
    var meta;
    var idle = "";
    if (!board.cuts.length) {
      offHtml = "<strong>—</strong><span>leave</span>";
      meta = "leave";
      idle = " idle";
    } else {
      var words = offcutPhrase(board.leftover, plan.desired);
      var short = words.indexOf("too short") === 0 || words === "no offcut";
      offHtml = "<strong>" + board.leftover.toLocaleString("en-US") + "</strong><span>mm offcut</span><span class='tag " +
        (short ? "short" : "keep") + "'>" + (short ? "too short" : "keep") + "</span>";
      if (!short) phrase = "<p class='phrase'>" + esc(words) + "</p>";
      meta = board.cuts.length + " cuts";
    }
    html += "<article class='board" + idle + "'><div class='meta'><span class='idx'>Board " + board.index +
      "</span><span class='stock'>" + board.stock + "</span><span class='cuts-n'>" + meta + "</span></div><div class='viz'>" +
      barSvg(board, job.kerf, colours, maxMm) + chipsHtml(board, colours) + phrase +
      "<p class='check'>" + esc(checkLine(board, job.kerf)) + "</p></div><div class='offcut'>" + offHtml + "</div></article>";
  });
  if (previous !== null) html += "</div>";
  if (!plan.boards.length) html += "<p class='note'>No available boards.</p>";
  var cutBody = document.getElementById("cut-body");
  if (cutBody) cutBody.innerHTML = html;
}

function rowFields(row) {
  var count = row ? row[0] : "";
  var length = row ? row[1] : "";
  return '<div class="edit-row"><label>Count <input inputmode="numeric" enterkeyhint="done" autocomplete="off" min="1" step="1" value="' +
    count + '"></label><label>Length mm <input inputmode="numeric" enterkeyhint="done" autocomplete="off" min="1" step="1" value="' +
    length + '"></label><button type="button" class="remove ghost">Remove</button></div>';
}

function fillForm(job) {
  document.getElementById("stock-rows").innerHTML = job.available.map(function (row) { return rowFields(row); }).join("");
  document.getElementById("piece-rows").innerHTML = job.desired.map(function (row) { return rowFields(row); }).join("");
  document.getElementById("kerf-input").value = String(job.kerf);
}

function readRows(container) {
  var rows = [];
  container.querySelectorAll(".edit-row").forEach(function (row) {
    var inputs = row.querySelectorAll("input");
    var count = parseInt(inputs[0].value, 10);
    var length = parseInt(inputs[1].value, 10);
    if (count > 0 && length > 0) rows.push([count, length]);
  });
  return rows;
}

function readJob() {
  var kerf = parseInt(document.getElementById("kerf-input").value, 10);
  if (!(kerf >= 0)) return null;
  return {
    kerf: kerf,
    available: readRows(document.getElementById("stock-rows")),
    desired: readRows(document.getElementById("piece-rows"))
  };
}

function validJob(job) {
  if (!job || typeof job.kerf !== "number" || !(job.kerf >= 0)) return false;
  if (!Array.isArray(job.available) || !Array.isArray(job.desired)) return false;
  return job.available.concat(job.desired).every(function (row) {
    return Array.isArray(row) && row[0] > 0 && row[1] > 0;
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
  if (editLink) {
    editLink.addEventListener("click", function () { edit.open = true; });
  }
  if (location.hash === "#edit") edit.open = true;
  edit.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(apply, 150);
  });
  edit.addEventListener("click", function (event) {
    var button = event.target.closest("button");
    if (!button) return;
    if (button.classList.contains("remove")) {
      var row = button.closest(".edit-row");
      if (row) row.remove();
      apply();
    }
  });
  document.getElementById("add-stock").addEventListener("click", function () {
    var box = document.getElementById("stock-rows");
    box.insertAdjacentHTML("beforeend", rowFields(null));
    var field = box.querySelector(".edit-row:last-child input");
    if (field) field.focus();
  });
  document.getElementById("add-piece").addEventListener("click", function () {
    var box = document.getElementById("piece-rows");
    box.insertAdjacentHTML("beforeend", rowFields(null));
    var field = box.querySelector(".edit-row:last-child input");
    if (field) field.focus();
  });
  document.getElementById("restore-sample").addEventListener("click", function () {
    try { localStorage.removeItem(STORAGE_KEY); } catch (err) { /* private mode */ }
    fillForm(SAMPLE);
    paint(SAMPLE);
  });
  var saved = null;
  try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null"); } catch (err) { saved = null; }
  if (validJob(saved)) {
    fillForm(saved);
    paint(saved);
  }
}

if (typeof document !== "undefined") boot();
