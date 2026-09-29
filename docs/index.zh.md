# DAF-MIT AeroMag

`dafmit-aeromag` 为 DAF-MIT AIA 开放飞行数据集提供简洁、明确的 Python 接口，用于航空器磁干扰补偿和 MagNav 研究。项目覆盖 Zenodo v3 中的 2020 年和 2021 年公开飞行数据，同时将大型 HDF5 文件保留在包外部。

本项目独立维护，不隶属于数据集作者或其所在机构，也不代表其获得这些方面的认可或背书。

公共接口经过有意控制，保持紧凑：

```python
from dafmit_aeromag import Dataset, Selection

data = Dataset()
frame = data.read(
    Selection(flight=2005, lines="2004.00"),
    columns=["mag_1_uc", "ins_lat", "ins_lon"],
)
```

请先阅读[快速开始](quickstart.md)，然后通过[数据模型](data-model.md)了解版本和 schema 细节。

读取使用显式的航次、航线和时间条件。上游 holdout 标记作为元数据提供，不参与样本过滤。实际样本覆盖和选择边界见[数据核验](data-audit.md)。
