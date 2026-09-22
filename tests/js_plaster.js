/* Compare the in-browser plaster cutter with Python.
   Stdin: { "job": { kerf_mm, available, desired, example? }, "custom": false }
   Stdout: { "plan": ..., "text": "..." }
*/
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const payload = JSON.parse(fs.readFileSync(0, "utf8"));
const job = payload.job;
const source = fs.readFileSync(path.join(__dirname, "..", "plaster_editor.js"), "utf8").replace(
  "__SAMPLE_JOB__",
  JSON.stringify(job)
);
const context = vm.createContext({console: console});
vm.runInContext(source, context);
const plan = context.packJob(job);
process.stdout.write(JSON.stringify({
  plan: plan,
  text: context.shopText(plan, job, !!payload.custom)
}));
