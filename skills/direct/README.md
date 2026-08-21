# RoadOfFlower 独立直连 Skill 索引

> 不是搬运另一张清单，而是直接进入原始仓库、读取固定提交中的实际 `SKILL.md`，再按实用性与来源多样性筛选。

## 当前结果

- 直接读取并入选：**500 条实际 Skill 文件**。
- 精选起步集：**300 条**。
- 来源仓库：**79 个**；应用分类：**14 个**。
- 其中官方来源记录：**110 条**。
- 与原 1,200 条聚合索引按名称未重合：**499 条**。
- 研究批次：`20260814T083654Z-4abed694e8`。

## 方法

1. 用多组 GitHub Repository Search 查询发现候选仓库；
2. 加入一组人工选择的官方、科学和维护者仓库，避免只按 stars 排名；
3. 固定每个仓库的 commit SHA，递归查找实际 `SKILL.md`；
4. 读取文件内容，解析 `name`、`description`、许可和兼容性字段；
5. 排除模板、示例、废弃项和明显恶意用途；
6. 根据来源、活跃度、元数据完整度、通用价值和任务清晰度评分；
7. 设置单仓库上限并轮询选取，防止一个大型集合垄断目录。

## 入口

- [完整直连索引](./INDEX.md)
- [精选 300](./USEFUL_300.md)
- [来源与固定提交](./SOURCES.md)
- [RoadOfFlower 独立检索与筛选方法](../../docs/07-independent-skill-research.md)
- [CSV](./catalog.csv) · [JSON](./catalog.json) · [元数据](./metadata.json)

## 状态含义

每条记录统一标记：

- `record_type=direct-skill-file`
- `install_status=not-installed`
- `verification_status=direct-file-fetched-frontmatter-parsed-not-audited`

这证明 RoadOfFlower 在本批次直接取得并解析了目标文件；不证明它已经安装、执行、安全审计或适用于你的环境。
