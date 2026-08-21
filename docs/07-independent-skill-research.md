# 独立 Skill 检索与实用性筛选方法

RoadOfFlower 不把单一聚合清单当作全部事实源。独立检索层会直接寻找原始 GitHub 仓库，读取固定提交中的实际 `SKILL.md`，再形成可追溯的候选目录和高实用性起步集。

## 为什么单独建立这一层

聚合清单适合提高召回率，却可能复制旧描述、遗漏仓库内新文件、混合广告链接与真实 Skill，也无法体现 RoadOfFlower 自己的判断。独立层承担四件事：扩大来源、直接核对文件、限制单一仓库支配、给出透明且可复算的实用性启发式。

## 检索范围

检索同时使用两类入口：

1. GitHub Repository Search：围绕 `agent skills`、`claude skills`、`codex skills`、`scientific agent skills`、`SKILL.md` 等查询发现候选仓库；
2. 人工种子仓库：覆盖 Anthropic、Microsoft、Hugging Face、Cloudflare、Firebase、Supabase、Sentry、Google Gemini、Vercel、科研工作流、Agent 工程、设计、知识管理、云平台和中文社区等来源。

种子不是白名单。动态检索仍可发现新仓库；种子用于确保官方、科研和专业垂直来源不会被 stars 排序淹没。

## 直接证据链

每条记录必须具有以下链路：

```text
repository search / seeded source
    → repository metadata
    → default-branch commit SHA
    → recursive Git tree
    → actual SKILL.md path
    → file content and frontmatter
    → normalized record
```

最终链接固定为：

```text
https://github.com/<owner>/<repo>/blob/<40-char-commit>/<path>/SKILL.md
```

因此后续上游修改不会悄悄改变该批次证据。

## 排除规则

默认排除：

- `examples/`、`fixtures/`、`templates/`、`testdata/`、`archive/`、`deprecated/` 中的样例或废弃文件；
- 没有可识别名称、描述过短或只写“sample/template”的条目；
- 明显面向凭证窃取、钓鱼、恶意软件、绕过认证、规避检测或垃圾信息自动化的内容；
- 无法固定提交、无法读取文件或不是实际 `SKILL.md` 的候选项。

防御性安全审计、漏洞检测与事件响应 Skill 可以收录，但仍不等于安全认证。

## 实用性评分

评分是可解释的排序启发式，不是客观质量真值。主要信号包括：

- 来源层级：官方维护、科学工作流、明确维护者、社区来源、搜索发现；
- 仓库活跃度、stars 与许可证线索；
- frontmatter 是否包含清晰 `name`、`description`、许可与兼容性；
- 描述是否明确任务、产物或使用条件；
- 是否覆盖测试、调试、研究、文档、数据、部署、安全、浏览器、GitHub、数据库、API、Agent、工作流等高频工作；
- 是否属于狭窄、产品私有或低迁移性的任务。

目录保留完整分数和分档，使用者可以不同意 RoadOfFlower 的排序，并直接用 CSV/JSON 重新排序。

## 多样性约束

如果仅按分数排序，大型社区仓库会占据大部分名额。独立层设置：

- 每仓库上限；
- 每个有效来源先保留少量高分条目；
- 按候选队列进行分数感知的轮询；
- 精选集继续限制单仓库和单分类占比。

这不是追求形式上的平均，而是防止单一来源把“有用”偷换成“文件数量多”。

## 真实性边界

每条直接记录标记为：

```text
record_type=direct-skill-file
install_status=not-installed
verification_status=direct-file-fetched-frontmatter-parsed-not-audited
```

它证明目标文件在固定提交中存在并被解析，不证明：

- 已安装或运行；
- 不含提示注入、危险命令或供应链风险；
- 依赖、许可证和客户端兼容性完整；
- 维护活跃或适合生产；
- RoadOfFlower 与发布者存在官方合作。

## 维护节奏

- 每月或按需重新运行动态搜索；
- 每次运行固定新的 commit SHA，并保留元数据与来源页；
- 对失效仓库、许可证变化和危险行为单独记录；
- 高实用性起步集应结合真实使用反馈调整，而不是只追逐 stars；
- 重要条目逐步增加人工审阅、最小权限检查和沙箱执行证据，但不得把未完成审计的条目提前标为安全。
