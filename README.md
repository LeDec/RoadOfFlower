# RoadOfFlower · Agent Skill 花路

> 让真正可用的 Agent Skill 更容易被发现、理解、组合与验证，让新人少走信息差造成的弯路。

RoadOfFlower 是一个**真实 Agent Skill 索引与学习项目**。这里不再用批量生成的名称冒充可用 Skill，也不要求你先安装任何东西：我们维护可点击、可追溯的外部 Skill 链接，并配套 Agent 入门、选型、工作流组合、定制、结果验证与风险控制教程。

## 当前规模

- **1,200 条真实 Skill 索引记录**，每条均指向现有外部页面或代码仓库。
- **75 个上游分类**，**216 个发布者或来源组织**。
- 来源：[VoltAgent Awesome Agent Skills](https://github.com/VoltAgent/awesome-agent-skills)，固定到提交 `947656d84432`。
- 本仓库没有安装或审计这些 Skill；统一状态为 `not-installed / indexed-link-not-audited`。

<!-- direct-index:start -->
## RoadOfFlower 自主检索层

除了固定版本的 1,200 条聚合索引，本项目还直接搜索 GitHub、检查原始仓库树并读取实际 `SKILL.md`：

- **500 条独立直连记录**，来自 **79 个仓库**；
- **300 条高实用性起步集**；
- 每条都固定到具体 commit，并记录来源、路径、评分和未审计边界；
- 入口：[独立直连索引](skills/direct/INDEX.md) · [精选 300](skills/direct/USEFUL_300.md) · [直接来源](skills/direct/SOURCES.md)。

这层目录由 RoadOfFlower 自己执行检索、文件解析、评分和多样性选择，不依赖单一聚合清单。
<!-- direct-index:end -->

## 快速入口

| 目标 | 入口 |
|---|---|
| 浏览完整索引 | [skills/INDEX.md](skills/INDEX.md) |
| 浏览独立直连索引 | [skills/direct/INDEX.md](skills/direct/INDEX.md) · [精选 300](skills/direct/USEFUL_300.md) |
| 下载数据 | [CSV](skills/catalog.csv) · [JSON](skills/catalog.json) |
| 关键词搜索 | `python scripts/search_skills.py "pdf" --limit 10` |
| Agent 入门 | [docs/01-agent-basics.md](docs/01-agent-basics.md) |
| 选择 Skill | [docs/02-find-and-evaluate-skills.md](docs/02-find-and-evaluate-skills.md) |
| 组合工作流 | [docs/03-compose-workflows.md](docs/03-compose-workflows.md) |
| 定制 Agent/Skill | [docs/04-customize-agent-and-skill.md](docs/04-customize-agent-and-skill.md) |
| 验证与风险 | [docs/05-verify-results-and-control-risk.md](docs/05-verify-results-and-control-risk.md) |
| 张明（zmz2）的愿望 | [wish/zmz2/README.md](wish/zmz2/README.md) |

## 项目如何工作

```mermaid
flowchart LR
    A[真实上游 Skill 索引] --> B[解析、规范化、去重]
    B --> C[CSV / JSON]
    B --> D[Markdown 与分类页]
    C --> E[本地搜索]
    D --> F[学习与选型]
    E --> G[组合、验证、实践]
    F --> G
```

## 三层内容

1. **发现层**：`skills/` 提供真实链接、发布者、分类、简介、原始仓库和来源提交。
2. **教学层**：`docs/` 从 Agent 基础讲到工具、工作流、定制、评测与风险控制。
3. **维护层**：同步脚本固定上游提交，验证器检查数量、唯一性、链接格式和真实性边界。

## 重要边界

- 被收录不等于安全、兼容、活跃或适合你的环境。
- 使用前必须阅读目标仓库的 Skill 文件、依赖、权限与许可证。
- 涉及删除、支付、发送、发布、账户权限、生产环境或隐私数据时，必须人工确认。
- RoadOfFlower 只做发现索引；外部 Skill 仍归各自作者所有。

## 为什么叫 RoadOfFlower

真正的“花路”不是一句祝福，而是一条不断维护的基础设施：有人补一条可靠链接，有人纠正一段错误简介，有人标出一个危险权限，有人把实践写成教程。每次维护都让后来者更接近自己的理想，而不是重复踩坑。

也祝愿 LED 在商业世界里成长为真正有分量的计算机技术大牛：技术判断扎实，商业选择清醒，产品被用户信任，团队愿意长期并肩，并且在成功之外保有健康、自由与内心踏实。🌸

<!-- wish-contribution:start -->
## 个人愿望区

Skill 与 Agent 教程仍是仓库主线。贡献者也可以在 `wish/<GitHub账号>/` 留下自己的愿望、路线图和祝福；个人内容不计入 Skill 数量。当前入口：[wish/zmz2](wish/zmz2/README.md)。
<!-- wish-contribution:end -->

## 贡献与许可证

贡献规则见 [CONTRIBUTING.md](CONTRIBUTING.md)。本仓库原创代码和文档采用 [MIT License](LICENSE)；第三方来源见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
