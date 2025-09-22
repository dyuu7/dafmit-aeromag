# DAF-MIT AeroMag

`dafmit-aeromag` 是面向 DAF-MIT AIA 开放飞行数据集的 Python 接口，用于航空器磁干扰补偿和 MagNav 研究。目前支持 Zenodo v3 版本，其中包含 2020 年和 2021 年的训练飞行数据。

本项目独立维护，不隶属于数据集作者或其所在机构，也不代表其获得这些方面的认可或背书。

[English](README.md) | [简体中文](README.zh-CN.md) | [文档](https://dyuu7.github.io/dafmit-aeromag/zh/)

HDF5 文件不会打包在本仓库中。首次使用时，文件会下载到可配置的缓存目录，并根据仓库内置目录中的校验和进行验证。

## 安装

```bash
python -m pip install dafmit-aeromag
```

如需转换为 xarray 数据集，可安装可选依赖：

```bash
python -m pip install "dafmit-aeromag[xarray]"
```

## 快速开始

```python
from dafmit_aeromag import Dataset, Selection

data = Dataset()

# 目录查询不会下载 HDF5 数据。
print(data.flights()[["flight", "collection", "date"]])
print(data.segments(2005, split="train"))
print(data.field_groups(flight=2005)[["group", "name", "units"]])

frame = data.read(
    Selection(flight=2005, lines=["2004.00"]),
    columns=["mag_1_uc", "ins_lat", "ins_lon"],
)
```

规范化结果以稳定的身份列 `flight`、`line`、`year`、`doy`、`tt` 和 `time` 开头。如果调用方需要不包含派生身份列的源字段，可以使用 `raw=True`：

```python
raw = data.read(
    [Selection.all(1002), Selection(flight=2005, tt=slice(54616, 55252))],
    columns=["mag_1_uc", "tt"],
    raw=True,
    missing="fill",
)
```

选择条件是显式的，并且始终限定在单个飞行架次内。航线使用类似 `"2005.20"` 的两位小数字符串表示；时间范围采用左闭右开语义。原生 `tt` 坐标和绝对 `time` 坐标是两种可选的筛选方式。读取默认使用 `split="train"`；如需读取文档记录的 holdout 区间，可以传入 `split="holdout"`，如需关闭分集过滤则传入 `split="all"`。请使用 `segments()` 查看上游记录的分段覆盖范围。

## 为什么要为这套数据提供封装？

上游发布版本和 Zenodo 记录是权威来源，但直接使用数据集时，需要自行协调大型 HDF5 文件、分散的 readme、字段定义、校验和以及训练集/holdout 分段元数据。2020 年和 2021 年文件的 schema 也不完全相同，而且航线标签并不总能单独确定包含它的飞行文件。

本项目把这些问题整合到一个可复现的接口中：版本化目录固定精确的源文件，下载结果会缓存并校验，选择条件明确限定飞行架次，分集选择可以显式控制，规范化的身份列和时间列让跨数据集分析更可预测。字段分组、备注、传感器位置和来源链接可以帮助用户发现数据，但不会重命名或隐藏原始 HDF5 字段。如果工作流需要直接处理文件，可以使用 `fetch()` 获取经过校验的本地 HDF5 路径；字段定义仍以上游说明为准。

## 数据来源与使用条款

[Zenodo v3 记录](https://zenodo.org/records/12723700) 是已发布文件、校验和及发布范围的权威来源。该记录附带的 readme 快照是本目录的主要语义依据；固定 revision 的上游 [MagNav.jl](https://github.com/MIT-AI-Accelerator/MagNav.jl) readme 提供稳定、可阅读的参考。研究数据受其自身的 [Data Sharing Agreement](https://github.com/MIT-AI-Accelerator/MagNav.jl/blob/b79a9ceed6009878f47c72938718f96ce067d803/readmes/DATA_SHARING_AGREEMENT.md) 约束；该协议与本仓库采用 MIT 许可证的代码相互独立。使用数据或再分发任何由数据生成的成果前，请先阅读[数据来源与使用条款](docs/provenance-and-terms.zh.md)页面。

## 文档

完整 API 和维护说明发布在 <https://dyuu7.github.io/dafmit-aeromag/>，也可以在 [`docs/`](docs/) 中查看。

## 开发

```bash
uv sync
uv run pytest
uv run ruff check .
uv run pyright
uv run python scripts/check_i18n.py
uv run mkdocs build --strict
```

项目要求 Python 3.10 或更高版本。目录更新脚本只会获取 Zenodo 元数据和较小的 readme 压缩包：

```bash
uv run python scripts/update_catalog.py
uv run python scripts/update_catalog.py --check
```
