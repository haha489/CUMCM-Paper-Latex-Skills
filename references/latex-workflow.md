# LaTeX 工程与编译

## 文件职责

```text
论文目录/
  main.tex                 主文件、标题、草稿开关与章节顺序
  preamble.tex             字体、页面、数学与图表配置
  data/results.tex         从 evidence.json 生成的统一结果文本
  sections/*.tex           摘要、共享章节、每问、评价与附录
  figures/                 当前项目使用的实际图片
  references.bib           已核实且实际引用的文献
  evidence.json            写作核查记录，不属于投稿正文
  写作核查.md               来源、技术追踪、编译与人工审阅说明
  论文完善建议.md           面向作者的缺口分析、图表建议与采纳记录
  build/                   编译日志及产出的 main.pdf
```

初始化：`python scripts/init_paper.py --output <新目录> --source-root <成果目录>`。输出目录必须为空，脚本不覆盖已有论文；同时复制独立的建议文档模板。已有工程只整合所需写法与核查功能，并新增或更新 `论文完善建议.md`，不强制迁移到本目录。

## 编辑

- `\PaperDrafttrue` 显示 `\FillIn{...}` 的编辑提示；写完后改为 `\PaperDraftfalse`。正式模式下残留提示会使编译报错。
- 骨架只有一个小问。复制为 `q02.tex` 等，并在主文件添加相应 `\input`；按题型选择标题，删除不适用小节。
- 最后的“模型评价”只含“模型优点”和“模型缺点”，缺点简短具体，细则见 [写作规则](writing.md)。各问实际完成的结果检验仍写在对应章节。
- `论文完善建议.md` 是单独交付的审阅文档，按 [建议文档规则](revision-advice.md) 填写，不转换为正文、附录或 `\input` 内容，也不因其中待决定的可选建议阻断交付。
- `\Result{id}` 使用生成的统一显示值；执行 `check_paper.py --write-results` 更新。它不做研究计算，只对已经核定的文本作安全转义。
- `references.bib` 初始为空，不提供假文献。以 `\cite{key}` 引用核实的条目；有引用时用 BibTeX 构建，编号按引用顺序。
- 默认普通 BibTeX `unsrt` 便于少依赖编译；有指定文献样式时更换并核验，不声称默认样式完全等同 GB/T 7714。
- 使用 `\includegraphics` 明确引入图片，文件缺失必须修复。中文图中文字应由绘图源生成，正文不贴代码截图替代数学公式。
- 可用 `\lstinputlisting` 纳入实际代码；中文注释较多时需按环境选择可靠的 Unicode 代码排版方案并视觉核查，不能擅自删去必须提交的程序内容。

## 编译

```text
python scripts/build_paper.py <论文目录>
python scripts/build_paper.py <论文目录> --engine <xelatex可执行文件路径>
```

脚本直接调用 XeLaTeX（禁用 shell escape 与交互提示），使用临时构建目录，不把旧 PDF 冒充本次成功；发现引用时运行 BibTeX，随后重跑交叉引用，保留日志。有环境限制时报出准确原因。自行使用命令亦可，例如：

```text
xelatex -no-shell-escape -interaction=nonstopmode -halt-on-error -file-line-error -output-directory=build main.tex
bibtex build/main
xelatex -no-shell-escape -interaction=nonstopmode -halt-on-error -file-line-error -output-directory=build main.tex
xelatex -no-shell-escape -interaction=nonstopmode -halt-on-error -file-line-error -output-directory=build main.tex
```

无引用时省略 BibTeX。工作目录为论文目录；命令必须配合可用的 TeX 环境，不自动安装大量宏包或修改全局配置。

旧材料 `豆包运行latex.txt` 的 WMI 桥接指向其他项目并写入其 PDF，不能直接复用。先检测当前引擎与日志；若确需桥接，应由当前任务的实际权限和环境决定，参数必须指向当前源文件与输出目录，不硬编码其他项目，也不绕过权限。

## 编译后

1. 检查退出状态和新 PDF，再检查 `.log` 中缺字、未定义引用、重复标签和越界盒子。
2. 用 PDF 渲染器逐页查看：摘要页、页面边距、正文连续性、公式、图表、代码附录和页脚。
3. 修复后重编译并重新查看受影响页面及后续分页。交付前对最终版本完整浏览。
4. `check_paper.py --final` 只覆盖静态可检查项，不检测所有宏展开、复杂 TeX 语法、每个数字、语义、身份信息或比赛页数；这些在人工核查记录中确认。

可用字体缺失时先选可用替代字体，记录排版变化；不把旧机器的“必然 DLL 失败”当作所有环境的规则。编译真正受阻时明确交付源工程及失败日志，不能说 PDF 已生成。
