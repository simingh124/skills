---
name: read-paper-pro
description: Read and summarize an arXiv paper from a title, arXiv ID, or arXiv URL (`abs`, `pdf`, `html`, `src`). Use this skill whenever the user asks to 读论文、总结 arXiv、分析方法/实验/训练细节、提炼研究思路，或直接给出论文标题 / 链接。 Resolve to the arXiv `src` endpoint, read the TeX source, and write a precise Chinese research note with linked prior work, inline figures/tables, and concrete follow-up ideas.
compatibility:
  tools:
    - bash
    - python
    - curl
  dependencies:
    - PyMuPDF
---

# Read Paper Pro

把 arXiv 论文整理成一份面向 AI 研究者的读论文笔记。坚持 **source-first**：优先下载 `src`，读取 TeX 源码，不要默认只看 PDF。

## Inputs

- 论文标题，例如 `Scaling Transformer to 1M tokens and beyond with RMT`

- arXiv ID，例如 `2304.11062` 或 `2304.11062v2`

- 任意 arXiv URL：`abs` / `pdf` / `html` / `src`

如果标题解析出多个候选，立刻停下让用户确认；不要猜。

## Paths

所有产物都放在**当前工作目录**：

- `./{paper_slug}/paper.tar.gz`

- `./{paper_slug}/source`

- `./{paper_slug}/reference_links.json`

- `./{paper_slug}/summary_{paper_slug}.md`

其中 `{paper_slug}` 由论文标题单词转成小写并用 `_` 连接，例如 `scaling_transformer_to_1m_tokens_and_beyond_with_rmt`。

开始下载前，先明确告诉用户这三个**绝对路径**：

- 下载路径

- 解压路径

- 总结路径

运行脚本时保持 shell 的当前目录仍然是用户当前目录，不要切到 skill 目录。

## Workflow

### 1. Resolve paper and source tree

运行：

```bash
python "<skill_dir>/scripts/prepare_arxiv_source.py" "<paper-title-or-url>"
```

如果系统没有 `python`，再改用 `python3`。

要求：

- 统一解析到 arXiv `src`

- 下载失败、压缩包损坏、解压失败时直接报错

- 不要静默回退到 PDF

### 2. Build a readable TeX view

如果论文跨多个 `\input{}` / `\include{}` 文件，运行：

```bash
python "<skill_dir>/scripts/collect_tex.py" \
  --entrypoint "<entrypoint>" \
  --output "<paper_dir>/combined_source.tex"
```

优先阅读：Abstract / Introduction / 方法 / 训练设置 / 核心实验 / 局限性。Appendix 只有在会影响总结时才读。

### 3. Scan visual assets

先运行首轮图片扫描：

```bash
python "<skill_dir>/scripts/prepare_summary_figures.py" \
  --entrypoint "<entrypoint>" \
  --paper-dir "<paper_dir>"
```

这一步只生成 `manifest.json`，并默认物化一张 `header.png`。不要在这一步把所有 PDF 图片都转成 PNG。

规则：

- 不要假设 Markdown 能稳定内联 PDF 图片

- 只把**最终总结实际会用到**的 PDF figure 转成 PNG

- 图片显示宽度优先参考 `figures/manifest.json` 里的 `suggested_width_pct`

- 只用论文源码里真实存在的图

- 如果图片定义在被 `\input{}` / `\include{}` 的子文件里，或使用 `\captionof{figure}`，也要照常纳入候选

### 4. Build links for prior work

运行：

```bash
python "<skill_dir>/scripts/extract_reference_links.py" \
  --source-dir "<source_dir>" \
  --output "<paper_dir>/reference_links.json"
```

写 related methods / 核心挑战时：

- 直接点名具体方法，不要写“许多已有方法”“另一类方法”

- 优先给方法名加链接，例如 `[Transformer-XL](...)`

- 如果方法名已经是 Markdown 超链接，**不要**再把整个链接包进反引号  
  对：`[Transformer-XL](...)`  
  错：`` `[Transformer-XL](...)` ``

### 5. Draft the summary and choose evidence

读取 `references/summary_prompt.md`，按其中结构写一版完整草稿，并先决定：

- 最终要展示哪些 `figure_id`

- 哪些重要表格要转成 Markdown 表格

- 每个单独展开的实验后面紧跟哪张图或哪张表

要求：

- 主体用中文；只保留必要 English 术语

- 表述精确、简洁、少空话

- 推断性内容显式标 `Inference:`

- 行与行之间留空行

- 关键概念、结论、限制用 Markdown **加粗**

- 开头至少放一张代表性头图

- 重要实验图/表必须放在对应实验描述之后，不要统一堆到节末

### 6. Materialize only the selected figures

草稿定稿后，按实际用到的图片运行第二轮：

```bash
python "<skill_dir>/scripts/prepare_summary_figures.py" \
  --entrypoint "<entrypoint>" \
  --paper-dir "<paper_dir>" \
  --clean \
  --figure-ids <figure_id_1> <figure_id_2> ...
```

然后写最终版 Markdown；只引用这次二次物化后真实存在的资源。

## Final checks

交付前确认：

- 结构遵循 `references/summary_prompt.md`

- 如果论文训练了模型，包含“训练方法”；否则删去该节并顺延编号

- 每个实验单元后面都有对应图或表

- 重要表格若做节选，明确标注“**表格节选**”

- 方法名超链接没有被反引号包裹

- Markdown 中引用的图片文件都真实存在
