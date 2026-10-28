# DocPilot / ProcureAgent 虚构练习数据

配套 [16 周主线](../../docs/learning-plan/enterprise-ai-16-weeks.md)和 [项目规格](../../docs/project-practice/projects.md)。目录仅包含数据与预期案例，API、索引、Agent、MCP 和部署仍需你逐阶段实现。

所有租户、项目、供应商与制度都是编造的教学样例，不作为采购或法律判断依据。不要替换成真实合同、供应商信息或业务凭据提交到公开仓库。

## 文件

- data/policies.json：当前/旧版制度、另一租户制度、恶意内容测试材料。
- data/projects.json：正常、多异常、资料不足、另一租户项目。
- data/suppliers.json：资格有效、资格过期、资料缺失与另一租户供应商。
- data/retrieval_cases.json：检索与来源隔离种子案例。
- data/review_cases.json：审查、审批、恢复与局部失败场景。

样例使用 section 引用，无真实 PDF 页码。W05 请自行创建或生成虚构 PDF 做解析，并人工校对页码映射；不能把这些 JSON 里的节号伪装成 PDF 页码。

## 固定约定

- 业务日期默认 2026-10-01，测试时显式传入，不依赖机器当前日期。
- 金额为整数分，百分比为整数百分点，例如 20 表示 20%。
- 制度有效区间为 valid_from <= as_of < valid_to；valid_to=null 表示没有设定截止日期。
- source_id 唯一标识某一来源版本。旧版与新版不能合并成同一个评测 ID。
- 服务端测试身份默认 tenant-a；数据中另有 tenant-b，不能由模型或请求体覆写身份。
- 预付款比例超过有效政策上限、报价超过预算、证书在业务日期前过期分别产生独立风险。
- 预付款或证书缺失返回资料不足，需要复核；不能推断符合要求。
- 示例中 certificate_valid_until 当天仍有效，as_of 超过该日期才算过期。

## 建议练习顺序

1. 用纯函数读取并校验 JSON，针对 P100/P200/P300 写确定性规则检查。
2. 用政策数据回答“当前/历史预付款上限”，记录正确 source_id。
3. 加入 tenant-a 与 tenant-b 的隔离案例，保证后者不进入前者提示。
4. 用 Mock API 暴露项目和供应商，再让工具调用它们。
5. 实现单 Agent 后用同一组数据比较图版与多 Agent 版。

P100 应无预设风险；P200 有三项明确风险；P300 有两项资料缺失。详细标签在 review_cases.json。review_cases 的故障项是测试设计，需自行构造超时、审批或重启，单独读取 JSON 不会自动制造故障。

种子案例数量较少，W07 请扩展到 20–30 个人工核对问题，另留验证样例；不要只针对固定项目 ID 硬编码规则。
