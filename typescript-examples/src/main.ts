import { parseAnswer } from "./contracts.js";
import { firstOrNull, mergePages, pick } from "./api-model.js";
import { mapLimit } from "./map-limit.js";
import { createSseParser, type SseEvent } from "./sse.js";
import { parseStreamEvent } from "./stream-events.js";
import { availableActions, describe } from "./state.js";
import { reduceAnswer, type AnswerState } from "./stream-state.js";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message);
}

const good = parseAnswer({
  answer: "预付款比例不得超过20%。",
  citations: [{ sourceId: "policy-a", quote: "不得超过20%" }],
  needsReview: false,
});
assert(good.ok, "合法回答应通过");
assert(good.value.citations.length === 1, "引用应保留");

for (const bad of [
  null,
  1,
  { answer: "x", citations: [], needsReview: false },
  { answer: "x", citations: [{ sourceId: "", quote: "q" }], needsReview: false },
]) {
  assert(!parseAnswer(bad).ok, `应拒绝: ${JSON.stringify(bad)}`);
}

const events: SseEvent[] = [];
const parser = createSseParser((event) => events.push(event));
for (const line of ["event: token", 'data: {"text":"预"}', "", "event: done", 'data: {"answerId":"A1","needsReview":true}', ""]) {
  parser(line);
}
assert(events.length === 2, "应解析两个事件");
assert(events[0]?.event === "token", "第一个是 token");
assert(events[1]?.event === "done", "第二个是 done");
const parsedEvents = events.map(event => parseStreamEvent(event.event, event.data));
assert(parsedEvents[0]?.type === "token" && parsedEvents[0].text === "预", "event 名与载荷必须一起解析");
assert(parsedEvents[1]?.type === "done", "终止事件也必须经过业务校验");

let state: AnswerState = { status: "idle" };
state = reduceAnswer(state, { type: "start" });
state = reduceAnswer(state, { type: "event", event: { type: "token", text: "预付款" } });
state = reduceAnswer(state, { type: "stop" });
assert(state.status === "stopped", "停止后应为 stopped");
const stoppedText = state.status === "stopped" ? state.text : "";
state = reduceAnswer(state, {
  type: "event",
  event: { type: "done", answerId: "late", needsReview: false },
});
assert(state.status === "stopped" && state.text === stoppedText, "迟到的 done 不应改回完成");

let calls = 0;
const mapped = await mapLimit([1, undefined, 3], 2, async (item) => { calls += 1; return String(item); });
assert(calls === 3 && Object.hasOwn(mapped, 1) && mapped.join(",") === "1,undefined,3",
  "mapLimit 不能跳过合法的 undefined 元素");

assert(describe({ status: "cancelled", reason: "用户取消" }).includes("已取消"), "状态应穷尽");
assert(availableActions({ status: "cancelled", reason: "x" }).length === 0, "取消后无动作");
assert(firstOrNull([]) === null, "空数组返回 null");
const merged = mergePages([{ items: [1, 2], nextCursor: null }, { items: [3], nextCursor: null }]);
assert(merged.join(",") === "1,2,3", "分页合并");
const picked = pick({ answer: "x", citations: [] }, ["answer"]);
assert(picked.answer === "x", "pick 保留键");

console.log("typescript examples: all checks passed");
