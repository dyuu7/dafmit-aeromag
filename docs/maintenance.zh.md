# 维护

## 更新目录

仓库内置目录有意固定到一个 Zenodo 记录。只有在检查上游发布版本和使用条款后，才应重新生成它：

```bash
uv run python scripts/update_catalog.py --record 12723700
uv run python scripts/update_catalog.py --check
```

脚本会解析 Zenodo API 响应和该发布版本的 readme 压缩包，不会下载 HDF5 数据。合并前请检查生成的差异，重点关注文件 URL、校验和、字段 schema 变化以及分段划分。上游 readme revision 固定在 `scripts/update_catalog.py` 中；采用新的元数据参考时应显式更新它。

如果 Zenodo API 临时不可用，可以使用仓库内已有的文件清单和上游 GitHub readme 刷新结构化元数据：

```bash
uv run python scripts/update_catalog.py --base-catalog src/dafmit_aeromag/catalog/v3.json
uv run python scripts/update_catalog.py --base-catalog src/dafmit_aeromag/catalog/v3.json --check
```

该回退路径不会发现新的 Zenodo 文件；如果要更换发布版本或文件清单，仍应使用基于 record 的常规命令。它也会有意使用固定的上游 revision，而不是可变的 `master` 分支。

## 文档翻译

`docs/` 下的每个页面都应同时有英文 `.en.md` 源文件和对应的中文 `.zh.md` 源文件。新增或修改页面时请保持两个文件同步，并在构建站点前运行配对检查：

```bash
uv run python scripts/check_i18n.py
```

## 监控上游

每周运行的 `upstream.yml` 工作流会跟踪 concept DOI；当发现更新的 Zenodo 记录时，它会创建或更新 GitHub issue。工作流不会自动修改 manifest，维护者必须检查发布内容，并有意识地决定是否更新目录。

## 发布检查清单

1. 运行完整的测试、lint、类型检查、文档构建和包构建任务。
2. 检查数据来源和数据许可链接。
3. 如果发布版本有意改变数据覆盖范围，更新目录和 changelog 说明。
4. 创建 `vX.Y.Z` 标签。发布工作流会创建对应的 GitHub Release 并附加构建产物，同时通过 PyPI Trusted Publishing 发布同一批文件。
