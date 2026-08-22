import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Run Bash in the current project. Batch related commands in one call when practical. Use grep/find/sed/cat, git diff, tests, compiler output, and normal shell syntax to inspect, edit, and verify work; avoid spending separate steps on trivial echo commands.",
  args: {
    command: tool.schema.string().describe("Bash command to run in the project"),
  },
  async execute(args, context) {
    const process = Bun.spawn(["bash", "-lc", args.command], {
      cwd: context.directory,
      stdout: "pipe",
      stderr: "pipe",
    })
    const [stdout, stderr, exitCode] = await Promise.all([
      new Response(process.stdout).text(),
      new Response(process.stderr).text(),
      process.exited,
    ])
    return `stdout:\n${stdout}\nstderr:\n${stderr}\nexit=${exitCode}`
  },
})
