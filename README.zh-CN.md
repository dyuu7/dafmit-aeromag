# DAF-MIT AeroMag

`dafmit-aeromag` 为 DAF-MIT AIA 公开飞行数据集提供 Python 接口，面向飞机磁干扰补偿和磁导航研究。它固定使用 Zenodo **v3**，包含 2020、2021 两个批次公开发布的 16 个航次文件。

[English](README.md) | [简体中文](README.zh-CN.md) | [文档](https://dyuu7.github.io/dafmit-aeromag/zh/)

这是独立项目，与数据集作者及其所属机构没有隶属或背书关系。大型 HDF5 文件按需下载到可配置的缓存目录，并按照包内固定发布清单校验。

## 安装

需要 Python 3.10 或更新版本：

```bash
python -m pip install dafmit-aeromag
```

## 查询目录、检查文件、读取样本

```python
from dafmit_aeromag import Dataset, Selection

data = Dataset(data_dir="./data")

# 离线查询：文档中的字段定义和段落标记。
print(data.flights()[["flight", "collection", "date"]])
print(data.fields(flight=2005)[["name", "units", "description"]])
print(data.field_groups(flight=2005))
print(data.segments(2005))

# 检查真实文件：缺失时下载，校验后报告实际字段。
info = data.inspect(2005)
print(info.sample_count)  # 6361
print(info.fields[["name", "dtype", "units"]])

frame = data.read(
    Selection(flight=2005, lines="2004.00"),
    columns=["mag_1_uc", "ins_lat", "ins_lon"],
)
```

航次标识一个文件；航线是文件内部的标签，编号不一定与航次相同。读取返回 pandas `DataFrame`，标准化结果以 `flight`、`line`、`year`、`doy`、`tt`、UTC `time` 六列开头。可以指定单个字段、有顺序的字段集合、表示全部物理字段的 `columns="all"`，或只取身份列的 `columns=[]`。

读取返回符合查询条件的真实样本，**不会自动按 train/holdout 过滤**。上游文件名保留 `_train.h5`，`segments().is_holdout` 保留来源文档的标记；它不表示数据质量差，也不证明样本已经公开。训练和评估子集由你的实验定义。[数据核验](docs/data-audit.zh.md) 记录了实际样本覆盖和选择边界。

## 明确的时间范围和批量行为

```python
frame = data.read(
    [Selection.all(1004), Selection(2005, tt=slice(54616, 55252))],
    columns=["mag_1_uc", "flux_a_x"],
    missing="fill",
)
```

时间区间包含起点、不包含终点。源时间 `tt`（午夜后秒数）和绝对时间 `time` 二选一。结果保留查询顺序和源文件顺序，重叠查询保留重复样本。默认每条查询都必须返回样本；预期可能为空时指定 `empty="allow"`，通过 `frame.attrs["selections"]` 查看各条查询的行数。

`missing="fill"` 用 `NaN` 填充已知但缺失的字段，未知名称和损坏的数据仍会报错。`fields()` 描述所属采集批次的字段，`inspect(flight).fields` 报告实际文件字段。合并两个批次时，这一区别尤其有用。

## 原始字段与源文件

```python
raw = data.read(Selection(2005), columns=["tt", "mag_1_uc"], raw=True)
source_path = data.fetch(2005)[2005]
```

原始模式不生成派生列。需要直接访问 HDF5 时使用校验通过的路径。复用同一个 `Dataset`，可在文件系统状态未变时复用成功的校验记录；`fetch(2005, recheck=True)` 强制完整复查。构造数据集时设置 `offline=True` 可以禁止下载。

## 文档与来源

建议先阅读[快速开始](docs/quickstart.zh.md)和[数据模型](docs/data-model.zh.md)。[在线文档](https://dyuu7.github.io/dafmit-aeromag/zh/)还包含 API 参考和维护说明。

文件、校验和及发布范围以 [Zenodo v3 记录](https://zenodo.org/records/12723700)为准。发布附带的 readme 快照提供目录语义，固定的 [MagNav.jl 版本](https://github.com/MIT-AI-Accelerator/MagNav.jl/tree/b79a9ceed6009878f47c72938718f96ce067d803/readmes)提供稳定来源链接。研究数据适用独立的[数据共享协议](https://github.com/MIT-AI-Accelerator/MagNav.jl/blob/b79a9ceed6009878f47c72938718f96ce067d803/readmes/DATA_SHARING_AGREEMENT.md)，与本仓库代码的 MIT 许可证分开。详见[来源与条款](docs/provenance-and-terms.zh.md)。

## 开发

```bash
uv sync --frozen
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run python scripts/check_i18n.py
uv run mkdocs build --strict
uv run python -m build
```

普通测试离线运行。真实文件测试和目录重新生成的方法见[维护指南](docs/maintenance.zh.md)。
