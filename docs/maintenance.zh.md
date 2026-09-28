# 维护

## 保持清楚的职责边界

公共接口由 `Dataset`、不可变的 `Selection`、检查报告 `FlightInfo` 和独立转换函数 `to_xarray` 构成。具体科学实验的划分规则留在读取器之外。

| 模块 | 职责 |
| --- | --- |
| `dataset.py` | 检查公共调用，协调目录、文件和读取操作，附加来源记录 |
| `selection.py`、`_validation.py` | 一次性规范化约束和有顺序的输入 |
| `catalog_core.py` | 私有的发布目录快照及返回独立副本的离线查询 |
| `storage.py` | 下载、字节校验及实例内校验记录 |
| `_hdf5.py` | 共享的文件结构与身份值检查 |
| `reader.py` | 真实样本字段发现、显式条件过滤、输出类型规划、文件资源生命周期 |
| `conversion.py` | 转换已经读取的表格，不依赖数据集状态 |

读取器不能根据 `is_holdout` 推断样本归属。缺失字段填充不能演变为损坏数据的恢复机制。已经能通过 `Selection` 或 `read` 参数表达的选择，不再增加另一套公共配置层。

## 更新目录

包内目录有意固定到一个 Zenodo 发布版本。明确准备采用或复查来源元数据时，重新生成：

```bash
uv run python scripts/update_catalog.py --record 12723700
uv run python scripts/update_catalog.py --check
```

这只下载发布记录和较小的 readme 压缩包，不下载 HDF5 数据。检查文件身份、日期、单位、来源链接及段落标记的差异。`is_holdout` 只保留上游说明，不断言可用性。GitHub readme 的版本固定在 `scripts/update_catalog.py` 中。

Zenodo 暂时无法访问时，可以复用已有文件清单，用固定版本的 GitHub readme 更新：

```bash
uv run python scripts/update_catalog.py --base-catalog src/dafmit_aeromag/catalog/v3.json
uv run python scripts/update_catalog.py --base-catalog src/dafmit_aeromag/catalog/v3.json --check
```

两个入口使用相同的目录组装逻辑，避免段落解释随获取路径不同而变化。后备方式改变的是元数据获取来源，不能发现新发布文件。修改发布版本或校验和需要走正常的 Zenodo 路径并审查。

## 不下载数据的验证流程

```bash
uv sync --frozen
uv run pytest --cov --cov-report=term-missing
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python scripts/check_i18n.py
uv run mkdocs build --strict
uv run python -m build
```

普通测试创建小型真实 HDF5 文件，并配套对应的测试目录校验和。覆盖公共行为、校验结果复用及失效、字段结构和坐标损坏、批量顺序与空结果、资源释放、xarray 转换。目录生成测试不依赖网络，比较两条获取路径的结果。持续集成覆盖 Python 3.10–3.14。

## 验证公开数据文件

```bash
MAGNAV_INTEGRATION=1 uv run pytest -m integration
```

这会核验分别属于两个批次的 Flt1004 和 Flt2005。已有原始文件时，可以复用本地副本并禁止联网：

```bash
MAGNAV_INTEGRATION=1 MAGNAV_DATA_DIR=/path/to/flight-files uv run pytest -m integration
```

固定的文件大小、校验和、预期行数及边界回归问题见[数据核验](data-audit.md)。源文件未变化时可以复用；不能为了掩盖真实的上游不一致而修改测试数据。定时集成测试工作流独立于普通持续集成运行。

## 文档与发布

每个文档页面都有配对的 `.en.md`、`.zh.md` 文件。修改时同步两种语言，运行配对检查，并以严格模式构建。示例或接口约定变化时，应针对合适的测试文件或公开文件执行示例代码。

每周的 `upstream.yml` 工作流跟踪概念 DOI，通过 GitHub issue 报告新版本，不会自动重写目录。维护者需要明确审查和采用新发布版本。

发布前完成测试、静态检查、格式与类型检查、文档及发行包构建，审查来源和条款链接、变更日志。保持 `pyproject.toml`、`__init__.py`、`CITATION.cff` 和 `uv.lock` 中项目版本一致。创建 `vX.Y.Z` 标签会触发配置好的发布工作流，创建 GitHub Release，并通过 PyPI Trusted Publishing 发布构建产物。
