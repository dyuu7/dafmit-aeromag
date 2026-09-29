# API

完整流程见[快速开始](quickstart.md)，顺序、字段及文件校验的详细约定见[数据模型](data-model.md)。下面的公共类型和异常都可以从 `dafmit_aeromag` 导入。

## 异常

所有领域异常继承 `DatasetError`；`InvalidArgumentError` 同时继承 `ValueError`。不支持的关键字参数遵守 Python 的常规行为，抛出 `TypeError`。

| 异常 | 含义及处理方向 |
| --- | --- |
| `UnknownReleaseError` | 选择包内已有版本（`v3`） |
| `UnknownFlightError` | 通过 `flights()` 查询有效的文件编号 |
| `UnknownFieldError` | 检查拼写、字段定义和实际文件检查结果 |
| `MissingFieldError` | 已知字段不在文件中；换字段或明确允许填充 |
| `InvalidArgumentError` | 根据提示修正输入类型、值或参数组合 |
| `DataUnavailableError` | 本地文件缺失、无法访问，或下载不能完成 |
| `DataIntegrityError` | 文件字节、结构或坐标检查不通过，或读取期间文件变化 |
| `NoDataError` | 查询没有匹配样本；修改条件或明确允许空结果 |

## 公共接口

::: dafmit_aeromag.Dataset
    options:
      show_root_heading: true
      show_object_full_path: false

::: dafmit_aeromag.Selection
    options:
      show_root_heading: true
      show_object_full_path: false

::: dafmit_aeromag.FlightInfo
    options:
      show_root_heading: true
      show_object_full_path: false

::: dafmit_aeromag.DatasetError
    options:
      show_root_heading: true
      show_object_full_path: false

::: dafmit_aeromag.InvalidArgumentError
    options:
      show_root_heading: true
      show_object_full_path: false
