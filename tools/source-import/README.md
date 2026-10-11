# 官方资料提取与复核

采集与审计脚本读取使用者指定的原始资料，输出到使用者指定的工作目录，不修改模型。七晶系注释脚本只有显式使用 `--publish` 才更新独立 App 注释变量。Python 3.10+、`curl` 和 Node.js 用于此次已验证的环境；Python 依赖单独安装：

```sh
python3 -m pip install -r tools/source-import/requirements.txt
```

原始 PDF、ZIP、页面渲染图与缓存应放在仓库外的私人工作目录，不随 App 发布。下面的 `/path/to/` 是需要替换的路径，脚本中没有开发者目录。官方公开下载仍须遵守来源条款；本目录没有提供书籍全文或通用照片再利用许可；新本地图只使用逐文件明确许可。

## IMA-CNMNC 七列名录

从 [官方名录](https://cnmnc.units.it/files/editor/IMA_Master_List_(2026-09).pdf) 取得源 PDF，再运行：

```sh
python3 tools/source-import/extract_ima.py \
  --pdf /path/to/IMA_Master_List_2026-09.pdf \
  --output-dir /path/to/output/ima \
  --version 2026-09 --expected-count 6239 --retrieved-at 2026-10-10
```

输出 JSON、CSV 和 `ima-extraction-report.json`。使用 PDF 表格及原字符坐标保留化学式上下标、官方七列和页码；不生成描述、属性或分类。检查源文件的日期、数量及 CC BY-SA 3.0 声明。更新版本时同时传入 `--source-url`，重新核对表格布局及提取质量，不能只改变数量参数。

2026-09 原 PDF 的 `CIDFont+F8` 字体在三条公式中输出私用字符：第 79 页 Gachingite、第 160 页 Orcelite 和第 201 页 Sluzhenikinite 已逐页渲染核对，分别保留 `≈`、`≤` 与空格的原意。提取程序只转换这三个已核对字形，其余私用字符会中止提取并要求复核，避免手机显示方框或猜测化学式。正式目录、来源复跑结果和离线校验清单必须同时更新；`validate_sources.py` 检查全部条目可复现及这三条原式。

## Handbook 选定物性事实

已核验的原始 89 个标签物性现在逐字段带有 `source_pdf_sha256`。`bind_physical_sources.py --repo /path/to/repo --sources /path/to/private/source-output` 先核对全部实际 PDF 和原字段，再仅增加来源哈希；名称、值、状态及原文均不改。`validate_sources.py` 按同一规则逐字段精确比较，晶系注释必须与事实的 PDF 哈希相等，缺失或变化会回到待复核。

新增物性导入的证据还须带有相邻 `index.json` 的 SHA-256 和拼版中的整数位置。程序核对该位置的矿物 ID、来源 URL、实际 PDF 哈希、页码和裁切坐标；同一张已看过的拼版不能证明另一个位置的资料。

`physical-targets.json` 是原项目 89 个标签的官方 PDF 来源清单，包含原数据缺项信息与未匹配的 16 个标签。它不是新推理类别列表。采集限最多 2 个请求同时运行，请求开始至少相隔 2 秒；本地复跑使用 `--offline`：

```sh
python3 tools/source-import/collect_physical_properties.py \
  --targets tools/source-import/physical-targets.json \
  --pdf-dir /path/to/private/physical-source-pdfs \
  --output /path/to/output/physical-candidates.json \
  --retrieved-at 2026-10-10 --offline
```

第一次取得公开官方 PDF 时去掉 `--offline`。源缓存保留内部追溯用途。采集脚本只摘录六个选定属性事实；输出中 `candidate` 状态不能导入产品。实测密度严格取 `D(meas.)`；`D(calc.)`、`n.d.` 与推测数据不当作已核验事实。原文的 Hexagonal、混合晶系、方向性硬度及数值范围不自动改写。

`physical-review-decisions.json` 保存此次逐页渲染核对的决定，包括手工纠正与待复核字段，绑定每个原 PDF 的 SHA-256。仅在源哈希完全一致时可复用：

```sh
python3 tools/source-import/finalize_physical_properties.py \
  --input /path/to/output/physical-candidates.json \
  --decisions tools/source-import/physical-review-decisions.json \
  --output /path/to/output/physical-properties.json \
  --report /path/to/output/physical-properties-report.json
```

此次输出应为 89 个标签、88 个唯一官方 PDF、477 个 verified 字段；32 个不确定解理值与 25 个未刊载字段的 `value` 保持 null。原 PDF 内容变化后应重新渲染逐页核验，并记录新的决定，禁止只替换旧决定中的哈希。不要使用 Python 的 `-O` 关闭提取/复核断言。

### 目录物性扩展

`reviewed-extension-batch001.json` 是另外100个精确 IMA 物种的六项选定事实和逐字段审核状态，不包含完整 PDF、图片或成因段落。100份源 PDF 已实际取得，源页标题、属性、负指数、方向及样品条件逐页核对并绑定原 PDF / 已看渲染图的 SHA-256。498项已核对；89项未刊载、11项待复核、2项只描述来源推定或合成类似物的字段保持 null。`complete=false` 指全目录尚未完成详录，不代表其余物种已经审核。

`extension-translations-zh.json` 只映射完全相同的已核对原值，保留合成、蜕晶质、温度、方向及不确定条件。数值直接保留。旧 Hexagonal 和 pseudohexagonal 不自动变成现代七晶系；有待另按实际点群复核。界面展开使用已核对的来源转录值，提取的 `raw` 留作审计，避免把丢失上划线的旧提取文字再次呈给读者。

```sh
python3 tools/source-import/import_reviewed_extension.py \
  --repo . --reviewed tools/source-import/reviewed-extension-batch001.json \
  --pdf-dir /path/to/private/extension-pdfs \
  --evidence-root /path/to/private/extension-review \
  --output-dir /path/to/output/extension-proposal
python3 -m unittest discover -s tools/source-import -p 'test_extension_import.py'
```

默认只生成提案；`--publish-to-app` 明确更新本地目录和 reference-manifest。原目录的名称、化学式、IMA字段、旧物性、模型标签、推理知识、权重和图库不改；已经导入的批次不能重复覆盖。仅在原PDF、已看渲染图与精确身份一致时允许导入，来源URL大小写与官方 www / 无www 原址保留。资料图鉴按实际记录计算核对范围：此批加入后185个规范物种、955项已核对物性；原89个兼容标签、477项标签字段含重复物种，不能与目录唯一种数混为同一统计。

扩展后运行完整 `validate_sources.py` 时，必须额外传入 `--reviewed-extension tools/source-import/reviewed-extension-batch001.json --extension-pdf-dir /path/to/private/extension-pdfs --extension-evidence-root /path/to/private/extension-review`。每个已导入批次的源JSON哈希必须一致，缺少源批次、重复物种、源图/PDF变化、翻译不匹配或原值变化都不能通过。这种来源一致性审计不证明照片识别、训练完成、独立样品的实测属性或Kappa目标。

### 产状与典型分布

`literature_contract.py` 从精确 IMA 身份、实际PDF字节、页数、字段裁切和已实际查看的拼图槽位核对来源。`import_reviewed_literature.py` 还要求外部明确提供 Root 逐字段 ledger 的可信 SHA；JSON 中的角色字符串不构成身份认证。原提案、查看索引、物性来源记录、字段和证据哈希必须完全相同；术语待核和未刊载状态不能提升。Root覆盖另绑定原字段、覆盖值、来源和证据哈希，不改原提案。

```sh
python3 tools/source-import/import_reviewed_literature.py \
  --repo . --proposal /path/to/private/detailed-facts-proposal.json \
  --index /path/to/private/viewed-render-index.json \
  --physical /path/to/private/reviewed-facts.json \
  --pdf-dir /path/to/private/extension-pdfs \
  --evidence-root /path/to/private/detailed-review \
  --ledger /path/to/private/root-field-review-ledger.json \
  --trusted-ledger-sha256 ROOT_INDEPENDENTLY_CONFIRMED_SHA256 \
  --output-dir /path/to/new-literature-staging
python3 -m unittest discover -s tools/source-import -p 'test_literature_import.py'
```

默认只写独立提案；`--publish-to-app` 仅明确应用到本地App资料文件，不部署网站。`literature_properties.occurrence/distribution` 保存简洁中文释义、短英文定位片段、源URL/PDF页与哈希、字段/证据/index/ledger哈希及审核状态。此批100种矿物中198字段为 `verified`（只核对文献对应关系），Achyrophanite产状为 `unavailable`，Adachiite产状为 `needs_review`，两者 `value_zh=null`。地点固定为该版文献非穷尽典型分布，不推断上传标本产地。全部目录还有大量未详细复核资料，`complete_all_minerals=false`；这批资料不证明图像识别能力。

独立 `window.MINERAL_LITERATURE_PROPERTIES.by_species` 按精确IMA ID与目录一致，不添加原105个推理／人工确认标签。原KB、模型、物性原值和晶系注释保留。reference-manifest的三文件加载合同不变，额外 `literature_bundle` 绑定完整 minerals.js 字节与Root ledger。所有原PDF、图像证据和长转录仍放在私人目录，未宣称Handbook全文／图片开放许可。

含这批资料的完整来源核验还需传入以下参数；缺少私有证据会失败，不将存在于目录的字段自动当作已审计：

```sh
  --literature-proposal /path/to/private/detailed-facts-proposal.json \
  --literature-render-index /path/to/private/viewed-render-index.json \
  --literature-physical-registry /path/to/private/reviewed-facts.json \
  --literature-pdf-dir /path/to/private/extension-pdfs \
  --literature-evidence-root /path/to/private/detailed-review \
  --literature-ledger /path/to/private/root-field-review-ledger.json \
  --trusted-literature-ledger-sha256 ROOT_INDEPENDENTLY_CONFIRMED_SHA256
```

### 七晶系与旧 Hexagonal 分类

旧手册的 `Hexagonal` 不直接作为七晶系中的“六方晶系”翻译。按 [IUCr 七晶系与点群表](https://it.iucr.org/Ac/ch1o3v0001/table1o3o4o3.pdf) 归类，三方和六方是两个晶系，同属 [六方晶族](https://dictionary.iucr.org/Crystal_family)。不能把晶族、晶系与晶格系统混为一项，也不能凭晶胞角度或照片选择多型。

`crystal-system-reviewed.json` 保留 23 份官方 PDF（24 个原标签，含 Elbaite 的两个旧键）逐页渲染检查的点群、矢量上划线、原值、PDF SHA-256 和渲染证据哈希。17 份单一三方、3 份单一六方；石墨、辉钼矿和氟磷灰石保留多型/结构条件，不任选一类。石英仅归类该页点群32和低于573°C的结构；不从照片推断当前晶相。Proustite 原页点群 `−3 2/m` 与同页空间群 `R3c` 不一致，均落在三方晶系，但具体点群仍待复核并向用户显示此差异。`pseudohexagonal` 保留原斜方或单斜归类。

```sh
python3 tools/source-import/annotate_crystal_systems.py \
  --minerals data/minerals.js \
  --pdf-dir /path/to/private/physical-source-pdfs \
  --output /path/to/output/crystal-system-annotations.json --publish
python3 -m unittest discover -s tools/source-import -p 'test_crystal_systems.py'
```

脚本只在源哈希、原字段与已渲染核对的点群匹配时生成 `window.MINERAL_CRYSTAL_SYSTEM_ANNOTATIONS`，追加到现有 `data/minerals.js`；不改原 KB、`verified_properties`、目录公式或原始晶系字段。未知点群、丢上划线或源文件变化会中止，不能靠改哈希绕过新的实际页面复核。IUCr 表本次通过官方网页读取；本机原 PDF 下载返回403，没有为其编造字节哈希。归类注释属于有出处的推导，不能证明照片中矿物身份或样品结构。

## 独立核验正式数据

`validate_sources.py` 只读正式 JSON、原 `data/minerals.js` 及私人源目录；仅写指定的摘要报告。Node.js 用于读取原 KB，可通过 `--node` 指定可执行文件。源目录需要当次已核验的 IMA JSON、物性 JSON、图片元数据、完整 IMA 署名文本、原名录 PDF、AMCSD ZIP 与私人物性 PDF 缓存。它不从网络取得数据。

```sh
python3 tools/source-import/validate_sources.py \
  --repo . --sources /path/to/private/reference-catalog \
  --re-extracted-ima /path/to/output/ima/ima-catalog-2026-09.json \
  --re-extracted-physical /path/to/output/physical-properties.json \
  --output /path/to/output/source-validation.json
```

全量检查 6,239 条七列数据及 Unicode/HTML 化学式、87 个原标签的官方公式、89 个物性标签、全部 9,895 条晶胞测量与原 ZIP 的一致性、原780条出处的保留与117个已审核本地图的逐文件来源/许可/像素/哈希状态、源文件及发布清单 SHA-256 和 IMA 署名文本。两个 `--re-extracted-*` 参数用于检查当次完整复跑一致性；省略时不报告该项已完成。

摘要含数量、原文件哈希、核验项与异常数，不含原 PDF、ZIP 文本、图片、Cookie 或凭据。返回码 0 表示这些一致性检查通过，1 表示存在异常。它不能代替照片许可裁定、像素质量检查、现场识别测试或模型准确率验证。

## 已审核真实参考照片出版

`publish_reviewed_reference_photos.py`读取已经完成逐图版权、来源、真实像素和跨批分组审核的登记，重新校验源下载/导图字节，最多选择每标签3个不同来源组。默认只输出独立提案；`--publish-to-app`才合并同source ID出处、复制原导图字节、输出逐图许可和审计、更新图片JSON的reference-manifest哈希。它不修改模型或冻结train/val/test，不能把来源标签当独立化验真值。输入registry包含真实坐标、SHA和review_evidence，未审核候选不可直接传入当准入图。

```sh
python3 tools/source-import/publish_reviewed_reference_photos.py \
  --dataset /path/to/private/reviewed-dataset \
  --registry /path/to/private/grouped-registry.jsonl \
  --proof-root /path/to/private/audit-project \
  --kb data/minerals.js --catalog data/catalog.json \
  --existing-image-sources data/image-sources.json --existing-assets-root . \
  --output /path/to/new-gallery-proposal --publish-to-app .
```

公开照片清单为 `data/reviewed-photo-assets.json`，每项path/bytes/sha256/source_asset_id；`data/licenses/reviewed-photos-v25.txt`与`reviewed-photo-attributions.json`保留作者、许可证、原页与裁切/缩放说明。2026-10-11版本117图/53原标签并不等于53个物种：Tetrahedrite仅有旧来源群名，不硬配现代Fe/Zn等后缀种；变种/群/集合体在schema中单列。
