# 雷达–视觉融合目标跟踪与轨迹预测

> 项目状态：准备阶段。本文整理研究问题、技术基础与已核验发表的代表性文献；算法、实验结果和工程配置尚未建立。

## 项目概述

本项目面向自动驾驶场景，研究**4D 成像毫米波雷达与相机融合的多目标跟踪、运动状态估计和短时轨迹预测**。预期输入为经过时间同步与空间标定的雷达点云、相机图像及自车位姿；预期输出为目标的三维位置、速度、航向、持续身份标识，以及未来 **1–3 秒**的多条候选轨迹和对应置信度。

研究重点是复杂条件下的可靠性：夜间、雨雾、强逆光、遮挡、密集切入和少见目标出现时，系统能否识别单一传感器的不可靠观测，并把感知的不确定性传递到预测结果中。项目拟先建立可复现的模块化基线，再探索检测、跟踪和预测之间的联合建模。

## 背景与问题分析

相机提供丰富的外观和语义信息，但单目图像的深度存在歧义，成像质量也会受光照和天气影响。毫米波雷达能够直接测量距离和**径向速度**，但返回点通常稀疏，可能含有杂波、虚警和多径反射。4D 成像雷达增加俯仰维观测，改善了三维定位能力，但仍不能把雷达点云简单当作激光雷达点云使用。[MSSF（T-ITS 2025）](https://doi.org/10.1109/TITS.2025.3554313)、[VoD 官方文档](https://github.com/tudelft-iv/view-of-delft-dataset)

本项目将问题分成四个相互影响的环节：

1. **对齐与表征**：时间戳、外参和自车运动误差会造成雷达点与图像目标错位；图像到鸟瞰视角的转换又受深度估计误差影响。
2. **检测与跟踪**：稀疏雷达回波、相似外观和短时遮挡会使目标漏检、重复检测或身份切换。
3. **状态与轨迹预测**：径向速度不能直接等同于目标完整速度；检测位置、航向及身份误差可能在预测阶段累积。转弯、让行和切入等行为需要多模态轨迹表示。
4. **长尾场景可靠性**：平均指标可能掩盖少见场景中的失败，需要按条件划分子集，并检查预测置信度是否与实际误差相符。

## 术语速查

| 中文术语 | 英文表达 | 含义及本项目中的作用 |
| --- | --- | --- |
| 4D 成像毫米波雷达 | 4D Imaging Radar | 通常指具有距离、方位、俯仰和多普勒速度信息的雷达；“4D”并非四维空间坐标。 |
| 多普勒速度 / 径向速度 | Doppler Velocity / Radial Velocity | 目标相对雷达沿视线方向的速度分量；需结合几何、连续帧或其他观测估计完整运动状态。 |
| 雷达散射截面（RCS） | Radar Cross Section (RCS) | 反映目标回波强度相关特征，受材质、姿态和距离等因素影响。 |
| 时空标定 | Spatiotemporal Calibration | 确定传感器时间偏移与坐标变换，使同一目标的观测可比较。 |
| 运动补偿 | Motion Compensation / Ego-motion Compensation | 利用时间戳和自车位姿，将不同采样时刻的点转换到统一参考时刻。 |
| 鸟瞰视角（BEV） | Bird's-Eye View (BEV) | 把图像与雷达特征映射到共同的平面表示。 |
| 视角变换 | View Transformation | 将图像特征通过深度估计或几何投影转换到三维空间或 BEV。 |
| 目标查询 | Object Query | 在 Transformer 类模型中表示候选目标的可学习特征，可跨帧更新以保持身份。 |
| 数据关联 | Data Association | 判断当前检测与已有轨迹是否属于同一目标。 |
| 身份切换 | Identity Switch (ID Switch) | 同一真实目标的跟踪 ID 被错误改变。 |
| 多模态轨迹预测 | Multimodal Trajectory Prediction | 为同一目标输出多种合理未来行为，而非仅输出一条平均轨迹。 |
| 预测置信度 | Prediction Confidence | 对候选轨迹概率或模型可靠性的估计，需要做校准检查。 |
| 开放集识别 | Open-set Recognition | 面对训练类别之外的目标时识别未知性，避免强行赋予已知类别。 |
| 长尾场景 | Long-tail Scenarios | 出现频率较低但具有重要风险或较高错误率的场景子集。 |

## 技术现状与可行路线

**雷达–视觉融合。** 现有工作包括点级/区域级关联、图像与雷达在 BEV 中融合，以及由目标查询从不同视角自适应采样。BEV 融合便于统一空间表示，但图像深度不准时可能把视觉特征放在错误位置；查询式与多阶段方法尝试在实例层面再次校正。[RCBEVDet](https://openaccess.thecvf.com/content/CVPR2024/html/Lin_RCBEVDet_Radar-camera_Fusion_in_Birds_Eye_View_for_3D_Object_CVPR_2024_paper.html)、[RaCFormer](https://openaccess.thecvf.com/content/CVPR2025/html/Chu_RaCFormer_Towards_High-Quality_3D_Object_Detection_via_Query-based_Radar-Camera_Fusion_CVPR_2025_paper.html)、[CVFusion](https://openaccess.thecvf.com/content/ICCV2025/html/Zhong_CVFusion_Cross-View_Fusion_of_4D_Radar_and_Camera_for_3D_ICCV_2025_paper.html)

**跟踪。** 先采用“逐帧检测 → 运动滤波 → 数据关联”建立可解释基线，借鉴雷达–相机置信度融合中的时间对齐、目标存在性判断与状态估计。再参考 ADA-Track 的交替检测与关联设计，研究如何加入雷达径向速度约束。原 ADA-Track 使用相机输入，雷达扩展需要本项目验证；遮挡恢复和身份切换应单独评估。[置信度融合跟踪（IEEE/CAA JAS 2025）](https://doi.org/10.1109/JAS.2025.125405)、[ADA-Track（CVPR 2024 主会）](https://openaccess.thecvf.com/content/CVPR2024/html/Ding_ADA-Track_End-to-End_Multi-Camera_3D_Multi-Object_Tracking_with_Alternating_Detection_and_CVPR_2024_paper.html)

**轨迹预测。** 从匀速/匀加速外推与运动学模型起步，再引入历史轨迹、目标交互与道路几何约束。以 MTR++ 的多目标意图建模作为阅读主线，参考 WAKE 研究观测缺失与物理可行性。明确区分真实历史、模型估计历史和带噪/缺失历史三种输入，统一 1–3 秒预测时长与候选轨迹条数。[MTR++（TPAMI 2024）](https://doi.org/10.1109/TPAMI.2024.3352811)、[WAKE（TPAMI 2025）](https://doi.org/10.1109/TPAMI.2025.3529259)

**不确定性与鲁棒性。** 分别记录传感器观测质量、目标存在性、状态估计协方差和轨迹模式概率，检验它们与真实误差的关系。以模态缺失、外参扰动、低照度及稀疏回波构造受控条件；不把检测分数直接当作预测置信度。将上游不确定性传给预测仍是本项目待验证的研究假设。[联合感知与预测综述（T-ITS 2025）](https://doi.org/10.1109/TITS.2025.3607743)、[WAKE（TPAMI 2025）](https://doi.org/10.1109/TPAMI.2025.3529259)

**联合建模。** 在模块化链路可评测后，参考 SparseDrive 的共享稀疏实例表示连接检测、跟踪与运动预测。其原始输入是相机；雷达如何接入可补读 SpaRC-AD，后者是正式 Workshop 论文，单列为工程参考。项目以周围目标轨迹预测为目标，不必同步实现自车规划。[SparseDrive（ICRA 2025 主会）](https://doi.org/10.1109/ICRA55743.2025.11128800)、[SpaRC-AD（ICCV Workshops 2025）](https://openaccess.thecvf.com/content/ICCV2025W/DriveX/papers/Wolters_SpaRC-AD_A_Baseline_for_Radar-Camera_Fusion_in_End-to-End_Autonomous_Driving_ICCVW_2025_paper.pdf)

### 建议的首轮实验

1. 选定数据集，完成时间戳、坐标系、相机内外参、雷达字段及标注格式检查；画出同一帧的图像、雷达投影和 BEV。
2. 建立纯视觉与雷达–视觉检测基线，先确认两者使用相同的类别、训练划分和评价范围。
3. 接入简单跟踪器及匀速轨迹外推，形成检测 → 跟踪 → 预测的端到端可评测流程。
4. 逐项加入多普勒约束、跨帧融合、遮挡恢复、多模态预测和不确定性传播，做消融实验。
5. 按天气、光照、遮挡、目标距离与目标类别等条件报告子集指标；对于没有可靠标签的场景，不做定量性能结论。

### 候选评测指标

| 环节 | 可关注的指标 | 注意事项 |
| --- | --- | --- |
| 三维检测 | mAP、NDS 或数据集官方指标 | 遵循各数据集的类别与匹配规则，跨数据集数值不可直接比较。 |
| 多目标跟踪 | AMOTA、ID Switch、召回率 | 同时报告连续性与身份稳定性。 |
| 轨迹预测 | minADE、minFDE、Miss Rate | 固定预测时长、候选轨迹条数和输入类型。 |
| 概率质量 | NLL、校准曲线、覆盖率等 | 先明确概率含义和评测协议，再选指标。 |
| 鲁棒性 | 子集性能与相对基线变化 | 样本数、场景定义及置信区间应一起报告。 |

## 候选数据集

| 数据集 | 适用性 | 使用前需要确认 |
| --- | --- | --- |
| [nuScenes](https://www.nuscenes.org/) | 相机、传统车载雷达、三维标注与跟踪/预测任务较完整，适合验证完整链路。 | 其雷达数据不能直接视作 4D 成像雷达数据；评测协议与传感器类型须单独说明。 |
| [View-of-Delft (VoD)](https://github.com/tudelft-iv/view-of-delft-dataset) | 包含同步的相机、激光雷达及具有俯仰和多普勒信息的雷达，适合 4D 雷达–视觉检测研究。 | 核实可用序列、跟踪标注及预测时长是否满足任务。 |
| [TJ4DRadSet](https://github.com/TJRadarLab/TJ4DRadSet) | 4D 雷达与相机研究的候选数据，包含连续序列和跟踪 ID 描述。 | 官方仓库注明公开下载内容及其他模态的获取条件有限制；先核实实际可获得的数据。 |
| [DSERT-RoLL（CVPR 2026）](https://openaccess.thecvf.com/content/CVPR2026/html/Cho_DSERT-RoLL_Robust_Multi-Modal_Perception_for_Diverse_Driving_Conditions_with_Stereo_CVPR_2026_paper.html) | 近期多天气与光照数据集，含 4D 雷达、相机、三维框、track ID 和里程计，可用于鲁棒性评测。 | 先核对可下载范围与连续标注长度；有 ID 不等于已提供目标轨迹预测协议。 |

## 已核验发表的代表性论文

**核验日期：2026-10-19；近三年窗口：2023-10-19 至 2026-10-19。** 下列正式版本均发表于 **2024–2026 年**，优先收录高水平期刊与强相关主会论文。期刊、主会、Workshop 分开标注；不收录仅有预印本且未完成正式发表核验的工作。原始技术若有更早预印本，不把正式出版年份误写为首次提出年份。

详细英文原题、出版证据、Zotero 占位、适用限制和调整记录见[项目论文库](论文库.md)。本轮无需为超期算法设置基础论文例外；VoD、TJ4DRadSet 等作为数据资源文档保留，不计入近期方法论文。

### 主线必读

| 方向 | 论文 | 正式发表 | 对项目的具体作用 |
| --- | --- | --- | --- |
| 任务框架 | [联合感知与预测综述](https://doi.org/10.1109/TITS.2025.3607743) | T-ITS 2025 · 期刊 | 确定检测、跟踪、预测的接口及误差传递问题。 |
| 4D 融合检测 | [MSSF](https://ieeexplore.ieee.org/document/10947638/) | T-ITS 2025 · 期刊 | 多阶段点云–图像交互，直接对应 VoD/TJ4DRadSet。 |
| 4D 融合检测 | [MLF-4DRCNet](https://www.sciencedirect.com/science/article/pii/S1566253526002563) | Information Fusion 2026 · 期刊 | 点、场景、候选框三级融合，作为近期强相关期刊对照。 |
| 融合检测基线 | [RCBEVDet](https://openaccess.thecvf.com/content/CVPR2024/html/Lin_RCBEVDet_Radar-camera_Fusion_in_Birds_Eye_View_for_3D_Object_CVPR_2024_paper.html) | CVPR 2024 · 主会 | 雷达编码、RCS 与 BEV 对齐，适合建立检测对照。 |
| 运动特征与融合 | [RaCFormer](https://openaccess.thecvf.com/content/CVPR2025/html/Chu_RaCFormer_Towards_High-Quality_3D_Object_Detection_via_Query-based_Radar-Camera_Fusion_CVPR_2025_paper.html) | CVPR 2025 · 主会 | 深度引导、目标查询、多普勒与历史雷达特征。 |
| 跟踪与状态估计 | [雷达–相机置信度融合跟踪](https://www.ieee-jas.net/en/article/doi/10.1109/JAS.2025.125405) | IEEE/CAA JAS 2025 · 期刊 | 时间对齐、存在性判断、匹配和融合状态估计。 |
| 三维身份关联 | [ADA-Track](https://openaccess.thecvf.com/content/CVPR2024/html/Ding_ADA-Track_End-to-End_Multi-Camera_3D_Multi-Object_Tracking_with_Alternating_Detection_and_CVPR_2024_paper.html) | CVPR 2024 · 主会 | 交替检测与关联；原始输入是多相机。 |
| 多模态轨迹预测 | [MTR++](https://ieeexplore.ieee.org/abstract/document/10398503/) | TPAMI 2024 · 期刊 | 多目标交互和意图查询；不能把 MTR 仓库直接视作完整 MTR++ 实现。 |
| 预测鲁棒性 | [WAKE](https://ieeexplore.ieee.org/document/10839301) | TPAMI 2025 · 期刊 | 历史观测缺失与运动学约束，适合遮挡/漏检实验。 |
| 联合任务工程 | [SparseDrive](https://doi.org/10.1109/ICRA55743.2025.11128800) | ICRA 2025 · 主会 | 连接检测、跟踪、预测的实例表示；雷达扩展需另行验证。 |

### 遇到具体问题再扩展

| 论文 | 正式发表 | 阅读触发条件 |
| --- | --- | --- |
| [CVFusion](https://openaccess.thecvf.com/content/ICCV2025/html/Zhong_CVFusion_Cross-View_Fusion_of_4D_Radar_and_Camera_for_3D_ICCV_2025_paper.html) | ICCV 2025 主会 | 候选框不稳，需要实例级跨视角细化。 |
| [R4Det](https://openaccess.thecvf.com/content/CVPR2026/html/Xia_R4Det_4D_Radar-Camera_Fusion_for_High-Performance_3D_Object_Detection_CVPR_2026_paper.html) | CVPR 2026 主会 | 位姿不准、时序对齐失败或小目标缺少雷达回波。 |
| [RPGFusion](https://openaccess.thecvf.com/content/CVPR2026/html/Qiu_RPGFusion_4D_Radar_Prior-Guided_Multi-Modal_Fusion_for_3D_Detection_CVPR_2026_paper.html) | CVPR 2026 主会 | 需要研究雷达置信度/深度先验与 BEV 采样。 |
| [RCTDistill](https://openaccess.thecvf.com/content/ICCV2025/html/Bang_RCTDistill_Cross-Modal_Knowledge_Distillation_Framework_for_Radar-Camera_3D_Object_Detection_ICCV_2025_paper.html) | ICCV 2025 主会 | 具备同步 LiDAR 训练数据，研究时序对齐与蒸馏。 |
| [DSERT-RoLL](https://openaccess.thecvf.com/content/CVPR2026/html/Cho_DSERT-RoLL_Robust_Multi-Modal_Perception_for_Diverse_Driving_Conditions_with_Stereo_CVPR_2026_paper.html) | CVPR 2026 主会 | 需要真实天气、光照条件与连续 ID 标注。 |
| [SpaRC-AD](https://openaccess.thecvf.com/content/ICCV2025W/DriveX/papers/Wolters_SpaRC-AD_A_Baseline_for_Radar-Camera_Fusion_in_End-to-End_Autonomous_Driving_ICCVW_2025_paper.pdf) | ICCV Workshops 2025 | 仅作雷达融合全链路补充；不属于主会或顶刊。 |

### 建议执行顺序

1. 读联合感知预测综述并核对数据集，先确认相机、雷达、连续 ID 与未来 1–3 秒标注是否可用。
2. 用 RCBEVDet/MSSF 确定一个可复现的检测起点，对照 MLF-4DRCNet；完成纯视觉与融合的公平比较。
3. 结合置信度融合跟踪和 ADA-Track，打通检测 → 跟踪 → 匀速外推，再定位身份和速度误差。
4. 用 MTR++、WAKE 指导多模态预测与历史观测退化实验；把阅读价值与代码可复现性分开判断。
5. 最后参考 RaCFormer、SparseDrive，验证雷达运动信息和共享表示是否改善全链路。扩展论文按失败案例选择。

论文中的性能数字只在各自数据集和协议下成立；不将检测提升直接解释为跟踪或预测提升，也不把所有方法一次叠加。

## 当前进度

- [x] 整理项目范围、背景、技术路线和已核验发表的代表性文献（2026-10-19 更新）。
- [ ] 确定数据集、任务边界和统一评测协议。
- [ ] 实现数据读取、标定检查与可视化。
- [ ] 复现检测、跟踪、预测基线。
- [ ] 完成长尾场景与不确定性实验。

本文为项目启动时的研究笔记。论文列表与实验方案应随复现结果和数据可用性持续更新。
