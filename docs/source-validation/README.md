# 资料核验报告

核验日期：2026-10-10。`summary.json` 为正式导入后的独立只读核验结果，`passed: true`、`anomaly_count: 0`。源文件位于内部工作目录，只有数量、来源和 SHA-256 进入此报告。

| 项目 | 核验数量与范围 |
| --- | --- |
| IMA 官方目录 | 6,239 个认可名称；七列及公式与原 PDF 全量复跑一致 |
| 原资料库 | 105 个原标签，其中 87 个公式与 IMA 官方值和页码一致 |
| Handbook 链接 | 5,366 个唯一匹配；不把 8 个歧义或 865 个未匹配记录猜填 |
| Handbook 物性（按原标签） | 89 个原标签、88 个唯一 PDF，477 个 verified 字段关联；含 Elbaite 的两个原标签 |
| Handbook 物性（按唯一 IMA 种） | catalog 中 85 个物种、457 个 verified 字段；硬度/密度/晶系各 85、解理 50、光泽 84、条痕 68 |
| 未核验/缺失物性 | 32 个 needs_review 与 25 个 unavailable 字段均为 null |
| AMCSD 晶胞文献 | 9,895 条记录、3,430 个 IMA 物种；测量值、空间群、源文件编号与原 ZIP 逐条一致 |
| 图片出处索引 | 780 条元数据、130 个矿物名；training_ready 为 0，未下载像素或训练 |

原 IMA PDF SHA-256：`2257c653491b346669ee5d38c98226a2bddbec0562a3675043730a01ca146973`。

原 AMCSD ZIP SHA-256：`82e217c0c5cb82d19dc591f7c18a91044731ea049542eb639f2a1915ebdf9761`。

`summary.json` 另列每个物性源 PDF 的哈希与对应原标签。核验决定仅适用于这些原文件；换源后重新审查。

保留的原采集报告：`ima-extraction-report.json`、`physical-properties-report.json`、`handbook-match-report.json`、`image-source-validation.json`。它们分别报告目录提取、经渲染核对的属性状态、精确名称匹配和图片元数据结构；后者没有执行像素质量或再利用许可裁定。

IMA 目录及其格式转换按 CC BY-SA 3.0 提供，完整署名/贡献者名单在 `data/licenses/ima-cnmnc-2026-09.txt`。Handbook 保留编辑者/MSA 引用、选定科学事实及官方链接，没有宣称 PDF 或正文获得开放转载许可。AMCSD 保留原论文与记录出处；公开下载不替代全文/照片再利用许可。Commons 许可逐图保留；RRUFF 照片许可仍未核实。详见 [资料来源说明](../../DATA-SOURCES.md)。

原项目的成因、用途及未替换的旧属性没有自动获得本次核验。目录、文献和图片来源数均不代表推理模型新增类别或现场准确率。可复跑脚本及依赖在 [tools/source-import](../../tools/source-import/README.md)。
