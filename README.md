# 雷达–视觉融合目标跟踪与轨迹预测

> 项目状态：准备阶段。本文整理研究问题、技术基础与候选文献；算法、实验结果和工程配置尚未建立。

## 项目概述

本项目面向自动驾驶场景，研究**4D 成像毫米波雷达与相机融合的多目标跟踪、运动状态估计和短时轨迹预测**。预期输入为经过时间同步与空间标定的雷达点云、相机图像及自车位姿；预期输出为目标的三维位置、速度、航向、持续身份标识，以及未来 **1–3 秒**的多条候选轨迹和对应置信度。

研究重点是复杂条件下的可靠性：夜间、雨雾、强逆光、遮挡、密集切入和少见目标出现时，系统能否识别单一传感器的不可靠观测，并把感知的不确定性传递到预测结果中。项目拟先建立可复现的模块化基线，再探索检测、跟踪和预测之间的联合建模。

## 背景与问题分析

相机提供丰富的外观和语义信息，但单目图像的深度存在歧义，成像质量也会受光照和天气影响。毫米波雷达能够直接测量距离和**径向速度**，但返回点通常稀疏，可能含有杂波、虚警和多径反射。4D 成像雷达增加俯仰维观测，改善了三维定位能力，但仍不能把雷达点云简单当作激光雷达点云使用。[雷达–视觉融合综述](https://arxiv.org/abs/2406.00714)、[View-of-Delft 数据集论文](https://repository.tudelft.nl/record/uuid:663863c1-35b8-48a5-9bc7-e775df8d7fac)

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

**跟踪。** 入门基线可采用“逐帧检测 → 运动滤波 → 数据关联”的流程，以量化漏检和身份切换。进一步可研究跨帧传播的目标查询，将检测和跟踪联系起来，并用雷达径向速度约束运动假设。遮挡恢复需要单独评估，不能只看总体检测精度。[UniAD](https://openaccess.thecvf.com/content/CVPR2023/html/Hu_Planning-Oriented_Autonomous_Driving_CVPR_2023_paper.html)

**轨迹预测。** 从匀速/匀加速外推与运动学模型起步，再引入历史轨迹、目标间交互和道路几何约束，预测多个未来假设。应明确区分“以真实历史框为输入”和“以模型检测/跟踪结果为输入”两种评测设置，后者才能反映上游误差的影响。[QCNet](https://openaccess.thecvf.com/content/CVPR2023/html/Zhou_Query-Centric_Trajectory_Prediction_CVPR_2023_paper.html)、[UniAD](https://openaccess.thecvf.com/content/CVPR2023/html/Hu_Planning-Oriented_Autonomous_Driving_CVPR_2023_paper.html)

**不确定性与鲁棒性。** 可分别记录传感器观测质量、检测分数、跟踪状态协方差和轨迹概率，再检验它们与真实误差的关系。模态缺失、外参扰动、低照度和稀疏回波可作为受控实验条件。将这些不确定性显式传给预测模块，是值得验证的研究假设，而不是已完成的功能。[联合感知与预测综述](https://arxiv.org/abs/2412.14088)、[SpaRC-AD](https://arxiv.org/abs/2508.10567)

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
| [View-of-Delft (VoD)](https://repository.tudelft.nl/record/uuid:663863c1-35b8-48a5-9bc7-e775df8d7fac) | 包含同步的相机、激光雷达及具有俯仰和多普勒信息的雷达，适合 4D 雷达–视觉检测研究。 | 核实可用序列、跟踪标注及预测时长是否满足任务。 |
| [TJ4DRadSet](https://github.com/TJRadarLab/TJ4DRadSet) | 4D 雷达与相机研究的候选数据，包含连续序列和跟踪 ID 描述。 | 官方仓库注明公开下载内容及其他模态的获取条件有限制；先核实实际可获得的数据。 |

## 可能相关的论文

以下是**阅读候选**，按与本项目的关系排列；论文中的性能数字只在其自身数据集和协议下成立。

| 方向 | 论文标题 | 阅读重点 |
| --- | --- | --- |
| 综述 | [A Survey of Deep Learning Based Radar and Vision Fusion for 3D Object Detection in Autonomous Driving](https://arxiv.org/abs/2406.00714)（2024） | 雷达–视觉融合方法分类与 4D 雷达背景。 |
| 融合检测 | [RCBEVDet: Radar-camera Fusion in Bird's Eye View for 3D Object Detection](https://openaccess.thecvf.com/content/CVPR2024/html/Lin_RCBEVDet_Radar-camera_Fusion_in_Birds_Eye_View_for_3D_Object_CVPR_2024_paper.html)（CVPR 2024） | 雷达特征编码与 BEV 跨模态融合。 |
| 融合检测 | [RaCFormer: Towards High-Quality 3D Object Detection via Query-based Radar-Camera Fusion](https://openaccess.thecvf.com/content/CVPR2025/html/Chu_RaCFormer_Towards_High-Quality_3D_Object_Detection_via_Query-based_Radar-Camera_Fusion_CVPR_2025_paper.html)（CVPR 2025） | 雷达引导深度估计、目标查询和跨视角采样。 |
| 4D 融合检测 | [CVFusion: Cross-View Fusion of 4D Radar and Camera for 3D Object Detection](https://openaccess.thecvf.com/content/ICCV2025/html/Zhong_CVFusion_Cross-View_Fusion_of_4D_Radar_and_Camera_for_3D_ICCV_2025_paper.html)（ICCV 2025） | 场景级提议与实例级多视角校正。 |
| 时序融合 | [RCTDistill: Cross-Modal Knowledge Distillation Framework for Radar-Camera 3D Object Detection with Temporal Fusion](https://openaccess.thecvf.com/content/ICCV2025/html/Bang_RCTDistill_Cross-Modal_Knowledge_Distillation_Framework_for_Radar-Camera_3D_Object_Detection_ICCV_2025_paper.html)（ICCV 2025） | 时序特征融合与跨模态蒸馏。 |
| 联合感知与预测 | [Planning-Oriented Autonomous Driving](https://openaccess.thecvf.com/content/CVPR2023/html/Hu_Planning-Oriented_Autonomous_Driving_CVPR_2023_paper.html)（UniAD，CVPR 2023） | 目标查询如何连接跟踪、运动预测与规划。 |
| 轨迹预测 | [Query-Centric Trajectory Prediction](https://openaccess.thecvf.com/content/CVPR2023/html/Zhou_Query-Centric_Trajectory_Prediction_CVPR_2023_paper.html)（QCNet，CVPR 2023） | 多模态轨迹生成与查询式解码。 |
| 雷达融合全链路 | [SpaRC-AD: A Baseline for Radar-Camera Fusion in End-to-End Autonomous Driving](https://arxiv.org/abs/2508.10567)（arXiv 2025） | 雷达信息如何进入跟踪、运动预测和规划；注意其为预印本。 |
| 联合任务综述 | [Joint Perception and Prediction for Autonomous Driving: A Survey](https://arxiv.org/abs/2412.14088)（arXiv 2024） | 感知误差传递、联合优化与评测问题。 |

## 当前进度

- [x] 整理项目范围、背景、技术路线和候选文献。
- [ ] 确定数据集、任务边界和统一评测协议。
- [ ] 实现数据读取、标定检查与可视化。
- [ ] 复现检测、跟踪、预测基线。
- [ ] 完成长尾场景与不确定性实验。

本文为项目启动时的研究笔记。论文列表与实验方案应随复现结果和数据可用性持续更新。
