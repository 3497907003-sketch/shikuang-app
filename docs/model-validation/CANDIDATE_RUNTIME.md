# 研究候选的显式 Web 诊断入口

当前默认识别仍使用原 `model-manifest.json`、98类、schema1、80,000,000字节模型上限和原决策规则。本入口只为受控工程验证准备；没有普通用户选择开关，没有候选权重或候选清单随本次修改进入生产，也未据此声称独立 Kappa、现场准确率或手机验收通过。

## 元数据与资源

`candidate-model.js` 提供严格的schema2契约及 `createManifest({version,classifier}, validatedLegacyManifest, legacyManifestSha256)` 元数据构造器。构造器不会读取或导出权重，不会补写训练或导出证据。

- 科学87类顺序精确绑定现有公开species-order文件的SHA `c167fa68e1019852a93d7b304237baf5ebe3e7ed4d0eb5a50b4e4dc1214c67bc`；每个输出索引分别映射同ID的原资料库条目，不重排或转换成旧98标签。
- `classifier` 必须显式给出id、role、path、bytes、sha256、classes、inputName、outputName、output、backbone、descriptor、fold、selectedEpoch和provenance。字段定义及完整**合成fixture**见 `tests/helpers/candidate.cjs`，该fixture不是可用权重或实际质量报告。
- 仅 `models/candidates/<真实SHA256>.onnx` 的绑定候选artifact可使用128MiB上限；必须是DINOv2-S14、CLS384、87类、float32、input/logits，fold0或1及其真实inner选择epoch。
- provenance包含真实训练计划、完成记录、选择锁、delta、官方base、capture kernel、导出器和导出完成记录的SHA；选择规则必须是inner CE，独立Kappa仍为null。禁止按outer分数挑fold或声称已经验收。
- 清单只接受当前App内 `research/candidates/<版本名>.json`；调用方必须另给该清单的真实SHA，禁止隐式默认URL、跨站地址或未绑定清单。
- gate绑定经schema1校验的旧manifest SHA和原1000类gate artifact。候选清单不会重定义旧gate的权重、温度或阈值。

## 浏览器 API

```js
const prepared = await MineralEngine.prepareCandidate({
  diagnostic: true,
  manifestURL: './research/candidates/实际版本.json',
  manifestSha256: '实际候选清单的64位SHA256',
  signal: controller.signal
});
const result = await MineralEngine.analyzeCandidate([{
  encodedPhoto: originalBlob,          // 原始JPEG/PNG/WebP Blob，不能是1536预览
  route: 'photo-file',                 // 照片来源与视频帧严格区分
  normalizedROI: {x0:0,y0:0,x1:1,y1:1},
  gateCropPercent: 1,                  // 旧gate独立的中心方形范围0.5–1
  limits: {inputMemoryBudgetBytes: 512*1048576, maxNativePixels: 40000000}
}], {diagnostic:true, prepared, signal:controller.signal, report:message=>{}});
```

这里的字符串占位符会被校验器拒绝。Root必须先准备真实、哈希绑定的候选清单与模型资源，才能进行实际运行验证。

视频或原生已经解码的帧应传入 `frame`，同时省略 `encodedPhoto`；frame遵循已有 `research-input.js` 的原尺寸、sRGB、方向、未预缩、来源及内存合同。`gateCropPercent` 与 `normalizedROI` 必须分别明确指定，不会把原页面中心裁切参数静默解释为研究ROI。

## 双路输入与生命周期

原图通过已有 `research-photo.decodePhoto` 解码一次。先将同一原尺寸帧按原 `cropCanvas` 中心方形／bilinear和 `MineralCore.pixelsToInput` 的旧final-cast规则生成gate张量，释放临时画布；随后将帧像素所有权交给已有native ROI／Q16／stepwise-f32 Worker，生成候选分类器的研究张量。两路缓冲区必须独立，研究张量不能供给旧gate。

这条gate路线直接使用原尺寸帧，旧普通页面通常先生成1536预览。二者的真实照片行为差异仍需实测；单元测试只核对各自的明确几何/数值规则和正确路由，不声称预览解码完全等价。

候选Worker重新核验两个manifest、所有模型的字节大小/SHA、真实输出形状与有限数值。gate执行完成并确认释放后才分配DINO。任何失败不返回部分候选。取消、整体120秒和Worker15秒启动上限会终止本次线程；错误后可重新开始。公开入口与普通识别、研究预处理共享同一活动任务门。

有Service Worker时，候选artifact使用独立no-store分支；重新核验候选和旧gate manifest、精确artifact URL、128MiB大小与SHA后才返回，不进入原模型缓存。生产schema1模型缓存和80MB校验继续保持。

结果只含raw87、逐图的catalog ID排名和诊断状态，不使用旧98类置信阈值、校准概率或隐式fold ensemble。`independentAcceptance=false`、`independentKappa=null`、`confidenceCalibrated=false` 必须保留。

## Android原生候选路径

Android安装环境中，同一个显式候选API在完成双路预处理后调用独立的`MineralInference.classifyCandidate`。原生端再次核对候选和旧gate清单、87类序、双profile、SHA和实际输出格式，并确认gate释放成功后才分配DINO。浏览器继续使用候选Worker。缺少该原生方法、候选清单或模型时会报错，不会改用旧生产模型或静默回退WASM。

原生资源清单必须随工程安装包显式准备；普通构建仍只包含原有生产权重。前端传入两份独立的float32 little-endian base64张量，取消和整体超时会向原生任务发送停止请求，晚到的监听器也会清理。该路径的合同、路由和故障处理软件测试已通过，候选权重的实际Android运行、数值一致性、设备内存和耗时仍待实测。

## 验证边界

Node行为回归验证契约、双路实际JS归一化、取消/重试、释放顺序、缓存隔离和构建依赖闭包；2026-11-04完整回归361项通过，构建171项离线资源，32项JS/MJS兼容检查通过。

同日使用本机Chrome 156和一张已用于训练的真实公开照片，实际执行两个fold的原图解码、双路预处理、gate和候选WASM推理。研究输入tensor与冻结参考SHA完全一致，两个87维输出相对训练端参考的最大绝对误差分别为1.416×10⁻⁵和1.311×10⁻⁵；两次调用完成后四个自有Worker均已终止。此记录只验证工程数值链路，训练照片不能作为独立准确率测试。

该次本机Chrome进程树采样峰值约2.21GB，不是精确的瞬时峰值，也不代表手机内存表现。此前一次失败由Playwright请求拦截改变Request.cache造成；移除拦截后按原no-store合同通过，没有放宽Service Worker校验。后续增加原生桥接后，完整Web回归367项通过；该次Chrome实测的Source版本在原生桥接加入之前。实体设备内存/耗时、未知/共生矿物拒判及独立Kappa仍未验收。
