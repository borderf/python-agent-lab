export type TaskState =
  | { status: "queued" }
  | { status: "running"; startedAt: string }
  | { status: "waiting_approval"; reportId: string; version: number }
  | { status: "completed"; receipt: string }
  | { status: "failed"; error: string }
  | { status: "cancelled"; reason: string };

export function assertNever(value: never): never {
  throw new Error(`未处理的状态: ${JSON.stringify(value)}`);
}

export function describe(state: TaskState): string {
  switch (state.status) {
    case "queued": return "排队中";
    case "running": return `运行中，开始于 ${state.startedAt}`;
    case "waiting_approval": return `等待批准：${state.reportId} v${state.version}`;
    case "completed": return `已完成：${state.receipt}`;
    case "failed": return `失败：${state.error}`;
    case "cancelled": return `已取消：${state.reason}`;
    default: return assertNever(state);
  }
}

export function availableActions(state: TaskState): string[] {
  switch (state.status) {
    case "queued":
    case "running":
      return ["cancel"];
    case "waiting_approval":
      return ["approve", "reject", "cancel"];
    case "completed":
    case "failed":
    case "cancelled":
      return [];
    default:
      return assertNever(state);
  }
}