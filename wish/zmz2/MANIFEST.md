# 愿望内容清单与校验信息

> 为避免自引用，哈希表不包含本文件自身。

| 文件 | 行数 | 字节数 | SHA-256 |
|---|---:|---:|---|
| `README.md` | 32 | 1986 | `f7ab67530a71b29e43d1ed008a9a7870b5e3b7d5fbc516c6ec1d9b90224b4b86` |
| `WISH_LIST.md` | 3190 | 173335 | `4dbb71d11ac3e1844499c87383457b61e5493172adf02bd04ced5f5d8137ea6a` |
| `assets/README.md` | 15 | 727 | `4836f50611a65694b23c7335811ca44d14b44efd325a2fb566a6f038569b8cba` |
| `assets/ai_research_roadmap.svg` | 7 | 1539 | `848642ac8f082061fb97ad290b8833dccb354b13e305ea88021549ba89809c17` |
| `assets/led_commercial_tech_growth.svg` | 4 | 1665 | `6a57684d3bb6aaece62b99392b28cec784a87c8ca5577ff1e20395bfd49121b9` |
| `assets/paper_flywheel.svg` | 4 | 1290 | `486032f83681a94dfe72190065c31cb312db231b3d5a651d4d8b5fa1031193da` |
| `attachments/01_RESEARCH_ROADMAP.md` | 132 | 5381 | `f860707cb38cfce22363ea19b32f89c14212618872df5df5fea5eeced51a4e20` |
| `attachments/02_PAPER_PIPELINE.md` | 184 | 6903 | `9b4ee2e79368b32df0df1352ee2e554cc411bd4656eda04ae8a824d74b1e8985` |
| `attachments/03_AI_LEADERSHIP_SCORECARD.md` | 164 | 5794 | `9653fe96f78826feb05b891632794c96f3d83a84f40af1b3e660b91f92074610` |
| `attachments/04_90_DAY_ACTION_PLAN.md` | 251 | 6471 | `5c0cebd8f84d347cdc305903ec9d265ead170ec8c92f427b6ad20c514eaa701a` |
| `attachments/05_LED_BLESSING.md` | 53 | 3308 | `a51a0b5a727b64af654074a2facce7a184dfac5b5669aead96f4e95bf79b16d6` |
| `attachments/06_IDEA_BACKLOG.csv` | 42 | 7042 | `20c993aab3311fec74e783c795de17d254a1c6c403776c4b361a8769d554f5e4` |
| `attachments/07_READING_LOG_TEMPLATE.md` | 73 | 1517 | `2ad23abf084b835a6849b96bb618d68865f2c3f89c2029948a4fe6ba2b00567d` |

## 结构检查

- 所有个人愿望文件位于 `wish/zmz2/`。
- `WISH_LIST.md` 超过 1,000 行并包含 120 个编号愿望。
- 三张 SVG 可由标准 XML 解析器打开。
- CSV 使用 UTF-8 编码并包含 41 条研究点子。
- Markdown 链接均使用仓库内相对路径。
