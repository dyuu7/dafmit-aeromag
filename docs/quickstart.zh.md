# 快速开始

## 查看目录

目录方法读取包内置的 JSON manifest，不会下载 HDF5 文件。

```python
from dafmit_aeromag import Dataset

data = Dataset(offline=True)
data.flights()
data.fields(flight=2005)
data.field_groups(flight=2005)
data.field_names("scalar_magnetometer", flight=2005)
data.sensors(collection="2021")
data.segments(2005, split="train")
```

`offline=True` 适合代码审查环境和可复现任务。它允许查看目录和读取本地文件，但如果所需文件不存在，会抛出明确的错误。

## 读取规范化数据

```python
from dafmit_aeromag import Dataset, Selection

data = Dataset(data_dir="./data")
selection = Selection(flight=2005, lines=["2004.00"])
frame = data.read(
    selection,
    columns=["mag_1_uc", "ins_lat", "ins_lon"],
)
```

前六列始终是 `flight`、`line`、`year`、`doy`、`tt` 和 `time`。`time` 使用 UTC；无时区时间范围会按 UTC 解释。当源文件没有存储完整的身份字段时，该值会根据飞行日期和原生时间字段推导。

## 读取多个飞行架次

```python
frame = data.read(
    [Selection.all(1002), Selection(flight=2005, tt=slice(54616, 55252))],
    columns=["mag_1_uc", "ins_lat"],
    missing="fill",
)
```

结果行先按选择条件的顺序排列，再按源数据顺序排列。对于显式列列表，`missing="raise"` 是默认行为。如果有意合并 2020 年和 2021 年的字段，可以使用 `missing="fill"`。

## 选择数据分集

`read()` 默认读取目录中标记为训练集的区间。holdout 数据和不进行分集过滤的源数据视图都需要显式指定：

```python
train = data.read(selection, columns=["mag_1_uc"], split="train")
holdout = data.read(selection, columns=["mag_1_uc"], split="holdout")
all_samples = data.read(selection, columns=["mag_1_uc"], split="all")
```

如果需要查看上游记录的航线和时间边界，请在按分集读取前使用 `Dataset.segments()`。字段分组只是发现字段的便利工具；完整语义请使用 `Dataset.fields()` 以及其中链接的上游 readme。

## 访问经过校验的源文件

如果工作流需要 HDF5 特有功能或规范化读取器之外的字段，可以使用 `fetch()`，再用熟悉的 HDF5 工具打开返回路径：

```python
paths = data.fetch(2005)
source_path = paths[2005]
```

返回的文件已经通过目录记录的大小、校验和以及 HDF5 可读性检查。

## 原生字段和 xarray

使用 `raw=True` 可以省略派生的身份列：

```python
raw = data.read(selection, columns=["tt", "mag_1_uc"], raw=True)
```

当 xarray 数据模型更适合后续处理时，可以安装可选依赖，并将返回的数据框转换为 xarray：

```bash
python -m pip install "dafmit-aeromag[xarray]"
```

```python
dataset = data.to_xarray(frame)
```
