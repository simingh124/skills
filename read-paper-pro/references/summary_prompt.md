# Summary Prompt

在读完论文源码后，按这个模板写最终总结。若某节对该论文确实不适用，只做最小幅度调整。

## Goal

写一份面向 AI PhD 学生的研究级读论文笔记：既要让读者准确理解论文贡献，也要让读者知道如何复现、如何评估、还能往哪里继续做研究。

## Hard requirements

- 主体使用中文；只保留通常不必翻译、翻译后反而失真的 English 术语，例如 `Transformer`、`memory token`、`attention`、`ablation`、`perplexity`、`benchmark`、`optimizer`。

- 不写客套话、空泛褒奖、重复背景；结论尽量锚定到 mechanism、assumption、training recipe、experiment、ablation 或 limitation。

- 如果某条判断不是作者明确写出的，而是你根据原文推得出的，显式标记 `Inference:`。

- 多用要点；**每条之间空一行**。关键概念、结论、限制与方向用 Markdown **加粗**。

- 如果 `./figures/header.png` 存在，标题和元信息之后必须插入头图。

- 如果某一部分明显需要图来说明，例如方法结构、主结果、复杂度曲线、attention 可视化，就插入对应图片，并补一条简短图注，说明“为什么看这张图”。

- **每个单独展开的实验**后面都要紧跟它自己的图或表；不要把图表统一堆在实验节最后。

- 图片优先用 `./figures/` 中已经物化好的文件，使用 HTML `<img>` 控制宽度；通常 `68%` 到 `78%`，较高或较窄的图用 `42%` 到 `60%`。若 `manifest.json` 提供了 `suggested_width_pct`，优先采用。

- 如果 `./reference_links.json` 里有 prior work 的链接，优先写成 `[方法名](链接)`。

- **不要**把整个 Markdown 超链接包进反引号；写 `[Transformer-XL](...)`，不要写 `` `[Transformer-XL](...)` ``。

- 如果论文有重要表格，尤其是主结果表、ablation 表、benchmark 总表，应转写为 Markdown 表格。若原表过宽，可只保留关键行列，并明确写成“**表格节选**”。

## Output template

```markdown
# <paper title>

- **arXiv**：<arxiv id>

- **一句话核心结论**：<最核心 claim>

<若有头图，在这里插入 HTML 图片标签>

*图注：一句话说明它为何最能代表全文。*

## 1. 问题定义

- 形式化说明论文要解决什么问题；交代输入、输出、目标、约束，以及真正被优化的核心对象。

## 2. 核心挑战

- 直接点名 2-4 个具体 prior methods，说明它们为何不足；不要写“许多已有方法”“另一类方法”“一些工作”。

- 难点来自 computation、memory、optimization、credit assignment、distribution shift 还是别的结构性限制，要说清楚。

## 3. 动机

- 用递进的问题链解释作者为什么会想到这个方案；写成第一性原理推导，而不是复述 introduction。

## 4. 方法

- 分点讲清 architecture、memory / retrieval / objective / inference flow。

- 对每个关键部件说明：它解决什么、怎么工作、与 prior work 的关键差异、代价或 trade-off。

- 若论文有关键公式、复杂度、更新规则或 objective，简洁写出。

<若适合，插入方法图和图注>

## 5. 训练方法

- 只有当论文确实训练了模型时保留这一节；否则删去并顺延编号。

- 尽量交代：初始化方式、backbone / 模型规模、memory token 数、window / segment / chunk 大小、optimizer、schedule、warmup、weight decay、gradient clipping、batch size、训练数据、样本构造、课程学习、BPTT、硬件与数值设定。

- 论文没写清的复现关键信息，要明确写“**论文未明确给出**”，不要编造。

## 6. 实验与评估

- 覆盖主实验、主要 ablation、外推 / 泛化实验、效率实验。

- 对每类实验说明：研究问题、baseline、数据集 / benchmark、metric、评估协议、最终现象。

- 让读者明确知道作者**和谁比、怎么比、结论是什么**。

- 每个实验描述后面立刻插入该实验对应的图或表。

## 7. 洞见与创新

- 先写至少两条 insight，并显式编号为 `Insight 1`、`Insight 2`。

- 然后先写一行：

  - （格式：**【创新点解决的问题】 -> 【受哪个 insight 启发】 -> 【设计了什么创新点】**）

- 创新点列表必须严格按这个格式写。

## 8. 潜在问题与后续方向

- 点明方法依赖的关键假设、最可能失效的边界、最值得继续深挖的 2-4 个 research direction，并说明其价值。

## 9. AI idea brainstorming

- 基于论文的方法、insight、实验现象或 limitation，发散出 3-5 个新的 AI research idea。

- 每个 idea 都必须具体到可以设计实验，至少说明：

  - 要解决的具体问题；

  - 继承了论文中的哪个 insight / 机制 / 观察；

  - 准备怎样改 architecture / objective / training pipeline / retrieval or memory mechanism；

  - 最小可行实验：数据、benchmark、baseline、metric；

  - 主要风险或失败模式。
```

## Quality bar

最终结果应帮助读者快速判断：

1. 论文真正贡献是什么；

2. 贡献依赖什么 insight；

3. 复现时要抓哪些训练与评测细节；

4. 它具体绕开、重组或超越了哪些 prior methods；

5. 方法最脆弱的地方在哪里；

6. 哪些延伸方向最值得继续做。
