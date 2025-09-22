# 从 `sgl2020` 迁移

0.2 版本是一次直接的破坏性变更，使用新的发行包名称 `dafmit-aeromag` 和导入命名空间 `dafmit_aeromag`。旧的 `sgl2020` 包及其有状态查询构造器不再提供兼容别名。

| 旧写法 | 新写法 |
| --- | --- |
| `from sgl2020 import Sgl2020` | `from dafmit_aeromag import Dataset, Selection` |
| `Sgl2020().line("1002.01").source(...).take()` | `Dataset().read(Selection(1002, lines="1002.01"), columns=[...])` |
| 手工维护的 2020 年 descriptions | `Dataset().flights()`、`.fields()` 和 `.segments()` |
| 隐式缓存和会变化的 DOI 目标 | 固定的 `v3` manifest 加可配置的 `data_dir` |

新 API 明确要求指定飞行架次，支持 2021 年文件，并提供规范化和原始两种输出模式。现有下游代码应迁移导入语句，并明确指定要读取的字段。
