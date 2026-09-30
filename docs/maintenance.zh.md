# 维护

## 保持清楚的职责边界

公共接口由 `Dataset`、不可变的 `Selection` 和检查报告 `FlightInfo` 构成。读取返回 pandas `DataFrame`；具体科学实验的划分规则和下游格式转换留在读取器之外。

| 模块 | 职责 |
| --- | --- |
| `dataset.py` | 检查公共调用，协调目录、文件和读取操作，附加来源记录 |
| `selection.py`、`_validation.py` | 一次性规范化约束和有顺序的输入 |
| `catalog_core.py` | 私有的发布目录快照及返回独立副本的离线查询 |
| `storage.py` | 下载、字节校验及实例内校验记录 |
| `_hdf5.py` | 共享的文件结构与身份值检查 |
| `reader.py` | 真实样本字段发现、显式条件过滤、输出类型规划、文件资源生命周期 |

读取器不能根据 `is_holdout` 推断样本归属。缺失字段填充不能演变为损坏数据的恢复机制。已经能通过 `Selection` 或 `read` 参数表达的选择，不再增加另一套公共配置层。

## 共享数据目录

本机缓存与共享目录使用同一套 `Dataset(data_dir=...)` 接口。共享可写目录应允许使用者创建文件、读取其他成员的数据文件，以及读写其他成员的隐藏锁文件。新文件遵循进程的 umask 与目录继承的 ACL；在 Unix 上，可配置共同用户组及 setgid 目录，配合 `umask 0007`，或配置默认 ACL。文件系统需要支持跨进程文件锁及同一目录内的原子重命名。

缺失文件的下载按目标文件加锁，在锁内重新检查是否已有其他进程完成下载；数据先在同一文件系统的临时目录中完成下载和校验，再原子移动到目标路径，下载失败时清理临时文件。锁文件会保留以维持稳定的文件身份。锁等待超过一小时或文件系统不支持锁时会报 `DataUnavailableError`，不退回到无锁下载。共享只读目录使用 `offline=True`，读取时不会创建锁文件。已有文件校验失败时，应由维护者核查来源并处理，不由库静默覆盖。

## 更新目录

包内目录及生成脚本固定使用 Zenodo v3，记录号为 `12723700`。解析器保留字段注释中的续行，遇到未识别的表格行、注释标题或重复身份时会报错，不会跳过后生成不完整目录。复查来源元数据或修改解析规则时，可重新生成目录：

```bash
uv run python scripts/update_catalog.py
uv run python scripts/update_catalog.py --check
```

这只下载发布记录和较小的 readme 压缩包，不下载 HDF5 数据。检查文件身份、日期、单位、来源链接及段落标记的差异。`is_holdout` 只保留上游说明，不断言可用性。GitHub readme 的版本固定在 `scripts/update_catalog.py` 中。

使用 `--output /path/to/catalog.json` 可写入另一个文件以便比较；`--check` 将生成内容与输出文件比较，不写入文件。Zenodo 暂时无法访问时，稍后重新运行即可。采用其他数据版本时，由维护者同步调整生成脚本、包内目录、测试和文档。

## 不下载数据的验证流程

```bash
uv sync --locked
uv run --no-sync pytest --cov --cov-report=term-missing
uv run --no-sync ruff check .
uv run --no-sync ruff format --check .
uv run --no-sync pyright
uv run --no-sync python scripts/check_versions.py
uv run --no-sync python scripts/check_i18n.py
uv run --no-sync mkdocs build --strict
uv run --no-sync python -m build
```

普通测试创建小型真实 HDF5 文件，并配套对应的测试目录校验和。覆盖公共行为、校验结果复用及失效、共享目录并发下载、字段结构和坐标损坏、批量顺序与空结果、资源释放。目录生成测试使用构造的发布元数据和 readme 压缩包，不依赖网络。持续集成测试 Python 3.10–3.14，并仅在 Python 3.13 上统计覆盖率。版本一致性检查、静态检查、双语页面配对检查、文档及发行包构建集中在独立任务中执行一次。各工作流通过 `uv sync --locked` 拒绝过期锁文件。发布流程复用同一套 CI 工作流，验证标签对应的提交并构建发行包。

## 验证公开数据文件

```bash
MAGNAV_INTEGRATION=1 uv run pytest -m integration
```

这会核验分别属于两个批次的 Flt1004 和 Flt2005。已有原始文件时，可以复用本地副本并禁止联网：

```bash
MAGNAV_INTEGRATION=1 MAGNAV_DATA_DIR=/path/to/flight-files uv run pytest -m integration
```

固定的文件大小、校验和、预期行数及边界回归问题见[数据核验](data-audit.md)。源文件未变化时可以复用；不能为了掩盖真实的上游不一致而修改测试数据。Data integration 工作流还会在线核对包内目录，并可通过 `workflow_dispatch` 手动触发；修改读取器、存储层或目录后，可针对相应分支运行。发布流程必须等待此工作流和普通 CI 均通过；Zenodo 暂不可用时不会发布。

## 文档与发布

文档说明当前接口和用法，数据核验记录保留影响结果解释的依据与修正。每个文档页面都有配对的 `.en.md`、`.zh.md` 文件。修改时同步两种语言，运行配对检查，并以严格模式构建。示例或接口约定变化时，应针对合适的测试文件或公开文件执行示例代码。

发布前完成测试、静态检查、格式与类型检查、文档及发行包构建，审查来源和条款链接。在 `pyproject.toml` 中设置包版本，同步更新 `CITATION.cff`，再运行 `uv lock` 刷新锁文件。运行时 `__version__` 读取已安装包的元数据，也适用于 `uv sync` 创建的可编辑安装。普通 CI 在同步项目后，核对引用文件与包元数据的版本是否一致。

创建 `vX.Y.Z` 标签会触发发布工作流，对该提交执行完整的 CI 与真实数据检查，并额外核对标签与包版本是否一致。可在本地运行 `uv run python scripts/check_versions.py --tag vX.Y.Z` 检查拟发布的标签。验证通过后，工作流通过 PyPI Trusted Publishing 发布此次验证中构建的同一份产物，再创建 GitHub Release 并附上发行包。每个标签只创建一次 Release，不覆盖已有 Release 及其附件。影响用法或结果的变化，可按需在对应的 GitHub Release 中简要说明。
