const form = document.querySelector("#search-form");
const query = document.querySelector("#query");
const status = document.querySelector("#status");
const results = document.querySelector("#results");
const cancel = document.querySelector("#cancel");
let active = null;

cancel.addEventListener("click", () => active?.abort());

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  active?.abort();
  const controller = new AbortController();
  active = controller;
  const timeout = setTimeout(() => controller.abort(), 5000);
  results.replaceChildren();
  cancel.disabled = false;
  status.textContent = "正在查询……";
  try {
    const response = await fetch(`/api/search?q=${encodeURIComponent(query.value.trim())}`, {
      signal: controller.signal,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "查询失败");
    if (active !== controller) return; // An older response must not replace a newer search.
    if (!Array.isArray(payload.items)) throw new Error("结果格式不正确");
    for (const item of payload.items) {
      const article = document.createElement("article");
      const heading = document.createElement("h2");
      const text = document.createElement("p");
      heading.textContent = `${item.title}（版本${item.version}）`;
      text.textContent = item.text; // Treat returned text as data, not HTML.
      article.append(heading, text);
      results.append(article);
    }
    status.textContent = payload.items.length
      ? `找到${payload.items.length}份虚构资料。`
      : "没有匹配资料，请尝试其他关键词。";
  } catch (error) {
    if (active !== controller) return;
    status.textContent = error.name === "AbortError"
      ? "已停止等待或查询超时，可以重新搜索。"
      : `未完成查询：${error.message}。请检查服务后重试。`;
  } finally {
    clearTimeout(timeout);
    if (active === controller) {
      cancel.disabled = true;
      active = null;
    }
  }
});
