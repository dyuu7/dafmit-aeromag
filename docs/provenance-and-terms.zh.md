# 数据来源与使用条款

`v3` 目录由 Zenodo 记录 [`12723700`](https://zenodo.org/records/12723700) 生成，该记录的概念版本为 [`10.5281/zenodo.4271803`](https://doi.org/10.5281/zenodo.4271803)。Zenodo 是已发布 HDF5 数据内容、校验和及发布范围的权威来源。上游 [MagNav.jl 仓库](https://github.com/MIT-AI-Accelerator/MagNav.jl)提供参考软件和元数据背景；本项目将 readme reference 固定到 [`b79a9ceed600`](https://github.com/MIT-AI-Accelerator/MagNav.jl/commit/b79a9ceed6009878f47c72938718f96ce067d803) 提交。

仓库内置目录包含 URL、校验和、文件大小、飞行日期、字段描述、字段备注、传感器位置以及分段元数据，不包含 HDF5 数据内容。更新脚本会获取 Zenodo API 记录和两个较小的 readme 压缩包，不需要下载训练文件。生成的字段和飞行元数据保留上游 readme 链接，而不是把这些文件复制到本仓库。

Zenodo v3 附带的 readme 快照是生成本目录的语义依据。固定版本的上游 readme 提供稳定的链接，便于查阅相关说明。研究数据另有单独的 [Data Sharing Agreement](https://github.com/MIT-AI-Accelerator/MagNav.jl/blob/b79a9ceed6009878f47c72938718f96ce067d803/readmes/DATA_SHARING_AGREEMENT.md)。该协议约束数据的使用，不会被本项目的 MIT 代码许可证取代。发布由数据生成的成果或再分发下载文件前，请特别检查其中的限制。

本仓库不主张拥有源数据的所有权。仓库内置目录是派生产物；字段分组和读取器行为属于本项目的接口层。引用和致谢应指向 Zenodo 记录及原始项目。
