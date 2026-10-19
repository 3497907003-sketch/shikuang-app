# 统一 JavaScript 构建兼容合同

构建目标为 Chrome 69。源码可以保留现代语法，但安装包、网页发布与离线缓存必须使用同一份 `dist/`，不能直接复制未编译源码。Android、桌面同步由各安装工程单独执行并核验；此构建本身不证明这些工程已同步。

离线运行 `npm test`、`npm run check`、`npm run build`、`npm run check:compat`。编译器是仓库内原样保存的 `@babel/standalone` 8.0.7，MIT，构建时校验 bundle、原包元数据、许可的长度与 SHA-256。来源、npm tarball 的 SHA-512/SHA-1 核验及未验证签名的边界保存在 `tools/vendor/babel-standalone-8.0.7.provenance.json`。不需要在线解析依赖，也不向产品交付编译器。

官方说明：[Standalone](https://babeljs.io/docs/babel-standalone)、[preset-env](https://babeljs.io/docs/babel-preset-env)。精确选项在 `tools/compat-target.json`：`env`、Chrome 69、保留原生模块、不隐式读取 Browserslist 配置、不自动注入运行时 polyfill。所有输出的 classic JS、Worker、Service Worker、vendor JS 与 MJS 共用该合同。`check:compat` 使用同一精确 parser 拒绝当前工程相关的目标后语法；这是有限静态门槛，不代替真实 Chrome 69 解析或执行。

`tools/build-inputs.json` 是安装工程可以静态读取并从同一 Git 提交复制的完整构建依赖清单，包含自身、构建规则、目标选项、编译器、许可和来源记录。全部原始离线资产及这些依赖共同生成确定的 shell 内容身份。先用该身份标记 HTML、core、Worker 和 Service Worker，再转译，避免转译格式改变后无法替换标记。Worker、其依赖和 ORT JS/MJS/WASM 使用同一版本查询；模型继续使用既有清单／权重身份和稳定模型缓存。

构建先验证资料、图库和生产模型，再在内存中完成全部编译和语法检查，写完整的同目录临时树。提交使用旧树备份及两次重命名；写入或提交失败恢复旧 `dist`。这是失败可回滚的完整树替换，并不声称支持目录交换原子性或任意进程终止后的自动恢复。

`compat.js` 仅提供本 realm 的 `globalThis` 及备份读取的 FileReader 后备。启动仍检查真实 Promise、URL、AbortController、SHA-256 和图片解码，缺少能力时保留中文恢复路径；不会因浏览器不支持源码中的 `?.`／`??` 而误拒绝已经编译的产品。原生迁移入口仍可独立注入旧缓存页面。

语法转译不能补出 WebAssembly SIMD、共享内存、真实解码或原生插件。当前 ORT WASM 仍有这些平台条件，旧 WebView 的完整本机识别需由已有 Android native ORT 路径及代表性设备回归证明。Worker 的 `ready` 仅证明脚本启动，不能当作 WASM 推理成功。真实 Android API24／30／35、桌面及网页断网升级与用户记录保留仍须在同步构建后独立验收；这些软件检查不证明识别准确率、独立 Kappa、发布或交付。
