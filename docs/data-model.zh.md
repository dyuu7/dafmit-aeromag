# 数据模型

## 版本和文件

本项目携带 Zenodo 记录 [`10.5281/zenodo.12723700`](https://doi.org/10.5281/zenodo.12723700) 的固定 `v3` 目录。每个飞行架次记录其数据集、日期、标准 HDF5 文件名、字节大小、MD5 校验和、采样间隔、飞行备注以及上游 readme 链接。

HDF5 文件会按需下载到 `Dataset.data_dir`。使用前会检查已有文件的大小、MD5 校验和以及 HDF5 可读性。损坏的本地文件会抛出 `DataIntegrityError`，不会被静默使用。

## 选择条件

`Selection` 是不可变的，并且始终限定在单个飞行架次内：

```python
Selection(flight=2017, lines=["2005.20", "2005.21"])
Selection(flight=1002, tt=slice(45100, 45200))
Selection(flight=1002, time=slice("2020-06-20T12:31:40Z", "2020-06-20T12:32:00Z"))
```

航线字符串会规范化为两位小数。通配符、范围和数值浮点数会被拒绝，以避免查询意外跨越飞行架次边界。`time` 和 `tt` 不能同时使用，两者都采用左闭右开范围。

目录会将分段序号与航线标签分开保存。一条航线可以在同一飞行架次内重复，一个航线标签也可能指向不同的测量飞行，因此 readme 中记录的飞行文件和时间区间仍然是权威信息。

## 输出模式

规范化输出以以下身份列为前缀：

| 列 | 含义 |
| --- | --- |
| `flight` | 文件/飞行架次标识符 |
| `line` | 保留两位小数的规范化航线标签 |
| `year` | UTC 日历年份 |
| `doy` | UTC 年内日序 |
| `tt` | 午夜以来的原生秒数 |
| `time` | 根据身份信息和 `tt` 推导的 UTC 时间戳 |

`raw=True` 只返回请求的一维源数据集。`N`、`dt` 和 `info` 等标量元数据不会作为样本数据提供。

`split` 参数控制目录分段如何暴露：

| `split` | 行为 |
| --- | --- |
| `"train"` | 默认值。排除标记为 `holdout` 的区间。 |
| `"holdout"` | 只返回标记为 `holdout` 的区间。 |
| `"all"` | 不应用目录中的分集掩码。 |

这样可以让默认训练数据路径排除 holdout，同时允许评估工作流显式请求这些区间。读取前请使用 `Dataset.segments()` 查看文档记录的覆盖范围。

2020 年和 2021 年的数据集字段并不完全相同。默认情况下，显式请求的字段缺失会快速失败；`missing="fill"` 会为选中文件中不存在的字段创建 `NaN`。`columns="all"` 会在文件打开后使用实际样本字段的并集，因此在 schema 差异是有意情况时，多飞行架次读取仍可以配合 `missing="fill"` 使用。

## 字段元数据和分组

`Dataset.fields()` 暴露原始字段名、单位、描述、数据集、字段备注和上游来源 URL。`Dataset.field_groups()` 增加了 `navigation`、`scalar_magnetometer`、`fluxgate`、`ins`、`current` 和 `voltage` 等稳定的便利分组；`Dataset.field_names()` 返回某个分组中的原始 HDF5 字段名。这些分组只用于发现字段，不取代上游字段定义。

`Dataset.sensors()` 暴露相对于前排座椅导轨记录的磁力计和通量门传感器位置。目录中的每一行都链接到对应的上游字段说明。完整的数据语义仍应参考[固定 revision 的 MagNav.jl readmes](https://github.com/MIT-AI-Accelerator/MagNav.jl/tree/b79a9ceed6009878f47c72938718f96ce067d803/readmes)，包括 [2020 年字段定义](https://github.com/MIT-AI-Accelerator/MagNav.jl/blob/b79a9ceed6009878f47c72938718f96ce067d803/readmes/sgl_2020_fields_readme.txt) 和 [2021 年字段定义](https://github.com/MIT-AI-Accelerator/MagNav.jl/blob/b79a9ceed6009878f47c72938718f96ce067d803/readmes/sgl_2021_fields_readme.txt)。

`Dataset.fetch()` 是访问原始数据的出口：它会下载并校验指定的 HDF5 文件，然后返回本地路径。本项目不会复制 HDF5 文件，也不会把完整的上游说明手工摊平成第二套 schema。
