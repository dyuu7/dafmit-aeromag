# 迁移到 0.4

0.4 有意替换了 0.3 中含义模糊的接口，不保留兼容别名。最关键的变化是样本选择：读取现在返回文件中符合你显式条件的真实样本，不再自动套用训练/holdout 过滤。

| 原先的用法或假设 | 0.4 的替代方式 |
| --- | --- |
| `read(..., split="all")` | 删除 `split`，现在普通读取就呈现真实文件 |
| 默认读取或 `split="train"` | 删除 `split` 并检查样本数变化，显式定义实验子集 |
| `read(..., split="holdout")` | 没有自动替代；对照说明和真实覆盖后，明确指定查询条件 |
| `segments(..., split=...)` | `segments(...)`，在返回表上查看或筛选 `is_holdout` |
| `split`、`released`、`has_holdout` 元数据 | 只在段落表保留 `is_holdout`，表示文档标注而非可用性 |
| 带 `available` 列的 `fields(flight=...)` | 只返回所属批次的定义；实际字段看 `inspect(flight).fields` |
| `field_names("ins", flight=2005)` | `field_names(group="ins", flight=2005)` |
| 把 `field_groups()` 当展开的字段表 | 它现在返回组名、说明、数量；组内成员用 `fields(group=...)` |
| `data.catalog` | 使用公共 `metadata` 和目录查询方法，返回独立副本 |
| `data.to_xarray(frame)` | `from dafmit_aeromag import to_xarray; to_xarray(frame)` |
| `InvalidSelectionError` | `InvalidArgumentError`，同时也是 `ValueError` |
| 批量查询中的空项被静默跳过 | 默认抛出 `NoDataError`；有意允许时用 `empty="allow"` |
| 构造后赋值修改数据集配置 | 用目标配置创建另一个 `Dataset` |

## 复查实验假设

Flt2005 现在返回 6361 个样本，而旧接口默认返回 6360 个。多出的那一行是之前被错误过滤的真实末尾转场样本，不是新发布的测试数据。[核验记录](data-audit.md) 解释了具体边界。

不要把 `split="holdout"` 机械替换为一组假定存在的样本。Readme 可能描述公开文件中根本没有的区间。`is_holdout` 既不是坏数据标记，值为假也不能证明有训练数据可读。可复现的评估应明确记录实验实际使用的航次、航线与时间子集。

## 清楚地区分查询目录与读取文件

```python
from dafmit_aeromag import Dataset, Selection, to_xarray

data = Dataset()
# 离线查阅文档，只返回 2021 批次的定义。
names = data.field_names(flight=2005, group="scalar_magnetometer")
# 确认实际字段，需要打开经过校验的文件。
actual_fields = data.inspect(2005).fields
frame = data.read(Selection.all(2005), columns=names, missing="fill")
array = to_xarray(frame)
```

`columns` 必须提供，全部字段也要明确写 `columns="all"`。单个字符串现在表示一个字段。`columns=[]` 表示六列标准化身份信息；`raw=True` 至少需要一个物理字段。可以直接传 Series、Index、一维数组和生成器，不接受集合或映射。构造查询时会检查时间边界，包括只有一端的开放区间。

`missing="fill"` 只处理字段不存在的情况，不掩盖未知名称、错误形状或损坏的坐标。有意允许空查询时使用 `empty="allow"`，并在 `frame.attrs["selections"]` 查看各条查询的行数。

复用同一个 `Dataset`，会在文件系统状态未变时复用校验成功记录。需要完整复查时调用 `fetch(..., recheck=True)`。xarray 的时间现在是 `datetime64[ns]`，而非对象数组；维度仍是 `sample`，以保留重复时间。

## 更早的 `sgl2020` 用户

发行包名为 `dafmit-aeromag`，导入名为 `dafmit_aeromag`。不再支持旧式有状态的查询构造器。将 `Sgl2020().line(...).source(...).take()` 这样的链式调用改为显式的 `Dataset.read(Selection(flight, lines=...), columns=...)`。文件的航次编号与航线标签必须分别提供。完整流程见[快速开始](quickstart.md)。
