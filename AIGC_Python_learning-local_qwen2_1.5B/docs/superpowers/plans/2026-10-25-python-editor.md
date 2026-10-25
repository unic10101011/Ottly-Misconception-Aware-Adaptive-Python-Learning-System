# Python 编辑体验实施计划

用户已确认：主线、加练和错题复习统一使用 CodeMirror 6，增加 Python 语法高亮、括号与引号配对、自动缩进及撤销重做。

**目标：** 让初学者顺畅编写 Python，同时保持原有判题、AI反馈、账号草稿和执行回放链路。

**结构：** `pythonEditor.mjs` 管理 CodeMirror 配置，`PythonEditor.jsx` 按需加载 `PythonEditorView.jsx`，后者管理编辑器生命周期；现有页面继续管理代码、草稿和请求。

**约束：** 不改判题器；只处理编辑区；保留当前工作区未提交的执行回放改动；缩进为4个空格；用户编辑不超过6000字；切题不共享撤销历史；程序更新代码不触发用户编辑回调。

## 任务一：可验证的编辑配置

文件：新增 `frontend/src/components/pythonEditor.mjs`、`frontend/tests/python-editor.test.cjs`，更新 `frontend/package.json` 与锁文件。

- [x] 安装 CodeMirror 的 state、view、commands、language、lang-python、autocomplete 及 Lezer 高亮模块，锁定实际版本。
- [x] 先写失败测试：Python字符串/注释/关键字有不同token；块末冒号回车增加4空格；Tab和Shift+Tab改变选中行缩进；括号、单双引号闭合及跳过已有闭合符号；只读和长度限制；编辑后撤销、重做。
- [x] 实现 `createPythonEditorState({code, onChange, readOnly, maxLength, readOnlyCompartment, label})`，使用官方语言扩展、快捷键和高亮；只读与长度检查由 transactionFilter 保护，外部代码同步通过显式注解区分。
- [x] 执行 `node --test tests/python-editor.test.cjs`，确认红绿过程。

## 任务二：共享组件与现有页面接入

文件：新增 `frontend/src/components/PythonEditor.jsx`、`frontend/src/components/PythonEditorView.jsx` 和 `frontend/tests/python-editor-dom.test.cjs`，修改 `frontend/src/components/CodeEditor.jsx`、`frontend/src/pages/MistakeDetail.jsx`、`frontend/src/styles/index.css` 及 `frontend/tests/submission-flow.test.cjs`。

- [x] 组件接收 `value`、`onChange`、`readOnly`、`label`、`documentId`、`className`，向ref提供 `focus()`；更新外部value不创建编辑回调；每个documentId重新创建编辑状态，卸载销毁view。
- [x] 主题保留现有深蓝编辑区与等宽字体，高亮色满足深色背景可读性；行号由CodeMirror维护；编辑区独立滚动。
- [x] 主线和加练继续通过原 `updateCode` 保存草稿、清除过期反馈；复习继续通过原 `editCode`，运行输入框保持普通文本框。
- [x] 保留现有运行/提交只读、重置后聚焦、执行回放及账号草稿隔离；移除旧文本框专用的Tab和行号滚动处理。
- [x] 调整页面测试的编辑组件替身，验证代码变更、重置、提交与复习仍传递正确内容。

## 任务三：验证和交付

- [x] 执行 `node --test tests/*.test.cjs` 与生产构建。
- [ ] 浏览器实际键盘验证：`print(`、单双引号、`if True:`回车、Tab/Shift+Tab、配对删除、Ctrl+Z/重做、中文输入、切题/草稿恢复和只读状态。
- [ ] 在主线、加练、复习入口分别确认新组件；检查窄屏编辑区不会撑宽页面。
- [x] 更新README说明快捷键及范围，记录实际验证结果和未覆盖项；保留队友未提交改动，不混入其他功能提交。
