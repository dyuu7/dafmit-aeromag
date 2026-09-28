# 快速开始

## 不下载数据，先了解数据目录

`Dataset` 表示一个已经发布的数据版本。**collection（采集批次）**在本项目中指采集年份（`"2020"` 或 `"2021"`）；**flight（航次）**标识一个文件；**line（航线标签）**标识文件中的测量记录。航线标签不一定以文件的航次编号开头，例如航次 2005 的文件包含 `"2004.00"`。

```python
from dafmit_aeromag import Dataset, Selection

data = Dataset(data_dir="./data")
data.flights()
data.fields(flight=2005)
data.field_groups(collection="2021")
data.field_names(flight=2005, group="scalar_magnetometer")
data.sensors(flight=2005)
data.segments(2005)
```

这些方法只读取包内的数据目录，不会下载文件。字段和传感器查询可指定 `flight=` 或 `collection=`，两者不能同时使用；都省略时返回所有批次。`fields(flight=2005)` 返回该批次**文档中的字段定义**，并不保证这个航次的文件拥有每个字段。

`segments()` 展示上游说明文件记载的区间。其中的 `is_holdout` 保留上游为评估预留数据的标记。它不是数据质量标记，也不能证明对应样本已经公开发布。读取数据时不会根据这些标记自动过滤。

## 检查实际文件，然后读取

```python
info = data.inspect(2005)
print(info.sample_count)  # 固定的 v3 文件中有 6361 个样本
print(info.tt_range)  # (54616.0, 55252.0)，实际观测到的最小值和最大值
print(info.fields[["name", "dtype", "units"]])

frame = data.read(
    Selection(flight=2005, lines="2004.00"),
    columns=["mag_1_uc", "ins_lat", "ins_lon"],
)
```

`inspect()` 和 `read()` 会下载缺失的文件，并按照目录中的信息校验。复用同一个 `Dataset`，可以避免对没有变化的文件重复计算校验和。若不允许下载，构造时指定 `offline=True`；本地缺少文件时会抛出 `DataUnavailableError`。

标准化结果以 `flight`、`line`、`year`、`doy`、`tt`、`time` 六列开头。`line` 是小数字符串；`tt` 是源文件记录的午夜后秒数；`time` 是 UTC 时间戳。源文件缺少身份字段时，根据目录中的航次编号和日期补齐。测量字段保留原始名称和单位。

## 明确选择哪些样本

```python
all_samples = data.read(Selection.all(2005), columns="mag_1_uc")
bounded = data.read(
    Selection(2005, tt=slice(54616, 55252)),
    columns="mag_1_uc",
)
assert len(all_samples) == 6361
assert len(bounded) == 6360

by_time = data.read(
    Selection(2005, time=slice("2021-12-21T15:10:16Z", "2021-12-21T15:11:00Z")),
    columns="mag_1_uc",
)
```

区间包含起点、不包含终点：`slice(a, b)` 表示 `a <= 坐标 < b`。允许一端为 `None`，但不能两端都省略。`tt` 与 `time` 二选一；同时指定航线和时间时取交集。没有时区的时间按 UTC 解释，有时区偏移的时间会转换为 UTC。

上例的最后一个样本实际存在于文件中，只有显式指定的 `tt` 区间才排除它。接口没有 `split` 参数：训练集和评估集的选择应由你的实验定义。实际文件的证据见[数据核验](data-audit.md)。

## 选择字段，处理文件间的差异

```python
# 只读取六列身份和时间坐标，适合检查覆盖范围。
coordinates = data.read(Selection(2005), columns=[])

# 读取实际存在的全部样本字段，同时补齐标准化身份列。
everything = data.read(Selection(2005), columns="all")

# 字段目录的查询结果可以直接传给 read。
names = data.field_names(flight=2005, group="scalar_magnetometer")
magnetic = data.read(Selection(2005), columns=names, missing="fill")

# 也可以直接使用实际字段表；其中不包含 HDF5 标量元数据。
native = data.read(Selection(2005), columns=info.fields.name, raw=True)
```

`columns` 必须显式提供，接受单个名称、有顺序的名称集合，或 `"all"`。列表、元组、pandas Series/Index、一维 NumPy 数组和生成器都可以；集合和映射会被拒绝。重复名称按首次出现的位置去重。

默认 `missing="raise"`：字段缺失即报错。`missing="fill"` 为已知但文件中不存在的字段填充 `NaN`。拼错字段名仍然抛出 `UnknownFieldError`，文件结构或坐标损坏仍然抛出 `DataIntegrityError`。`raw=True` 仅返回文件中真实存储的字段，因此不接受派生的 `time` 或空字段列表。

## 合并查询，明确处理空结果

```python
combined = data.read(
    [Selection(1004, lines="1004.02"), Selection.all(2005)],
    columns=["mag_1_uc", "flux_a_x"],
    missing="fill",
)

documented_but_absent = data.read(
    Selection(1004, lines="4014.00"),
    columns="mag_1_uc",
    empty="allow",
)
assert documented_but_absent.empty
print(combined.attrs["selections"])
```

结果先按查询顺序排列，每条查询内部保留源文件行顺序。重叠查询会保留重复样本。默认情况下，**任何一条**查询没有样本都会抛出 `NoDataError`，即使同批其他查询成功也一样。`empty="allow"` 允许这些空查询；全部为空时仍保留完整列结构和类型。每条查询的 `row_count` 都会写入 `frame.attrs["selections"]`，包括返回零行的查询。

## 访问源文件，或转换为 xarray

```python
source_path = data.fetch(2005)[2005]
data.fetch(2005, recheck=True)  # 强制重新检查大小、校验和与基础结构。
```

需要标量元数据（`N`、`dt`、`info`）或其他 HDF5 功能时，用 h5py 打开 `source_path`。`inspect().dt` 是文件声明的采样间隔，不代表数据没有时间缺口。

安装 `dafmit-aeromag[xarray]` 后，可以使用可选转换功能：

```python
from dafmit_aeromag import to_xarray

array = to_xarray(frame)
hours = array.time.dt.hour

# 本例只有一个航次，时间有序且不重复，可以显式作为索引。
by_timestamp = array.swap_dims({"sample": "time"})
window = by_timestamp.sel(time=slice("2021-12-21T15:11:00", "2021-12-21T15:12:00"))
```

转换结果使用 `sample` 维度，因此允许时间戳重复。`time` 是真正的 `datetime64[ns]` 坐标，数值表示 UTC，并附有 `timezone="UTC"` 元数据。在自己的分析中改用时间作维度之前，应检查时间是否有序且唯一。xarray 的标签切片包含两端，与 `Selection` 的左闭右开区间不同。
