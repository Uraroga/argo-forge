import { tool } from "@opencode-ai/plugin"

export default tool({
  description: "Run one Bash command in the current project. Use it to inspect, create or edit files, compile, run tests, read errors, and continue the coding loop.",
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
    return `${stdout}${stderr}exit=${exitCode}`
  },
})
