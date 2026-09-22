/* Compare the in-browser cutter with Python. Reads one job from stdin:
   { "kerf": 3, "available": [[count, length]], "desired": [[count, length]] }
   Writes boards as [stock, cuts, tsv leftover], unallocated, and lumber text.
*/
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const job = JSON.parse(fs.readFileSync(0, "utf8"));
const sourcePath = path.join(__dirname, "..", "planker_editor.js");
const source = fs.readFileSync(sourcePath, "utf8").replace(
  "__SAMPLE_JOB__",
  JSON.stringify({ kerf: job.kerf, available: job.available, desired: job.desired })
);
const context = vm.createContext({ console });
vm.runInContext(source, context);
const plan = context.buildPlan(job);
process.stdout.write(JSON.stringify({
  boards: plan.boards.map(function (board) {
    return [board.stock, board.cuts, board.leftover];
  }),
  unallocated: plan.unallocated,
  lumber: context.lumberLines(job, plan),
  offcut270: context.offcutPhrase(270, plan.desired),
  offcut11: context.offcutPhrase(11, plan.desired)
}));
