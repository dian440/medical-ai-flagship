# P0 控制实验结果（2026-11-12）

> 目的：把先验匹配后**校准跨度收缩**里的「样本量效应」与「患病率效应」分离。
> 权威口径自检：24/24 项与 `multi_model_prior_matched.json` 完全一致。

## 一、主结论

- 8 个 组合中 **排序有任何改变** 的有 8/8；**最佳数据集身份改变** 的有 7/8。
- 8 组合平均效应分解（对数尺度）：**样本量份额 13.1%**，**患病率份额 86.9%**。
- BH-FDR（16 组 DeLong）：原始 p≤0.05 共 **7** 组，FDR 校正后 **7** 组显著。

## 二、逐组合（跨度 = max/min ECE，同一标签内三库比较）

| 组合 | raw 全样本 | native169（原生先验） | matched169（共同先验） | 完美校准地板 matched169 | 样本量份额 | 患病率份额 | 最佳库改变率 |
|---|---|---|---|---|---|---|---|
| NIH/PNEUMONIA | 3.295× | 3.101× | 1.670× | 1.089× | 9% | 91% | 88% |
| NIH/NORMAL | 2.760× | 2.539× | 1.358× | 1.135× | 12% | 88% | 49% |
| CHEX/PNEUMONIA | 1.293× | 1.320× | 1.474× | 1.247× | 15% | 85% | 98% |
| CHEX/NORMAL | 4.437× | 3.914× | 2.225× | 1.097× | 18% | 82% | 0% |
| MIMIC_CH/PNEUMONIA | 5.043× | 3.880× | 1.991× | 1.219× | 28% | 72% | 13% |
| MIMIC_CH/NORMAL | 5.017× | 4.862× | 1.379× | 1.258× | 2% | 98% | 100% |
| MIMIC_NB/PNEUMONIA | 2.052× | 1.967× | 1.548× | 1.197× | 15% | 85% | 98% |
| MIMIC_NB/NORMAL | 5.398× | 5.057× | 1.281× | 1.176× | 5% | 95% | 100% |

## 三、逐对翻转率

| 配对 | 翻转率 | Monte Carlo 95% CI |
|---|---|---|
| NIH_vs_KEM | 82.3% | [82.2%, 84.5%] |
| NIH_vs_VIN | 44.7% | [82.2%, 84.5%] |
| KEM_vs_VIN | 58.0% | [82.2%, 84.5%] |

## 四、数据集层面符号翻转检验（n=8）

- 观测中位率差：**+15.17 个百分点**（相对交换性零假设期望 83.3%）
- 单侧 p = **0.0312**（最小可达 0.0039）

## 五、Q7 校准斜率/截距（全样本）

| 组合 | 数据集 | slope | intercept | calib-in-the-large | Brier |
|---|---|---|---|---|---|
| NIH/PNEUMONIA | NIH | 0.4824 | -3.2100 | +0.2389 | 0.1169 |
| NIH/PNEUMONIA | KEM | 0.9110 | +1.3716 | -0.2927 | 0.2550 |
| NIH/PNEUMONIA | VIN | 0.5802 | +0.1303 | -0.0788 | 0.2193 |
| NIH/NORMAL | NIH | 1.1713 | +3.8946 | -0.4359 | 0.2394 |
| NIH/NORMAL | KEM | 4.8135 | -0.0888 | +0.1672 | 0.1814 |
| NIH/NORMAL | VIN | 2.1181 | +0.8245 | -0.1261 | 0.2061 |
| CHEX/PNEUMONIA | NIH | 0.4787 | -3.1440 | +0.2057 | 0.1145 |
| CHEX/PNEUMONIA | KEM | 1.7194 | +1.8522 | -0.2036 | 0.1288 |
| CHEX/PNEUMONIA | VIN | 1.0178 | +1.2844 | -0.1590 | 0.1649 |
| CHEX/NORMAL | NIH | 0.4844 | +4.1104 | -0.4736 | 0.3180 |
| CHEX/NORMAL | KEM | 2.6460 | +1.7789 | -0.0521 | 0.0976 |
| CHEX/NORMAL | VIN | 1.2985 | +0.6386 | -0.0942 | 0.1600 |
| MIMIC_CH/PNEUMONIA | NIH | 0.3876 | -3.4551 | +0.3085 | 0.1559 |
| MIMIC_CH/PNEUMONIA | KEM | 0.6396 | +0.9509 | -0.2066 | 0.2368 |
| MIMIC_CH/PNEUMONIA | VIN | 1.0829 | -0.2024 | +0.0458 | 0.2133 |
| MIMIC_CH/NORMAL | NIH | 0.5997 | +4.0655 | -0.5174 | 0.3397 |
| MIMIC_CH/NORMAL | KEM | 2.5353 | +1.2758 | +0.0020 | 0.1631 |
| MIMIC_CH/NORMAL | VIN | 1.5430 | +1.2344 | -0.2145 | 0.2456 |
| MIMIC_NB/PNEUMONIA | NIH | 0.7880 | -3.5302 | +0.3758 | 0.1920 |
| MIMIC_NB/PNEUMONIA | KEM | 1.0994 | +0.9057 | -0.1985 | 0.2230 |
| MIMIC_NB/PNEUMONIA | VIN | 2.1814 | -0.7209 | +0.1279 | 0.2318 |
| MIMIC_NB/NORMAL | NIH | 0.5887 | +4.1877 | -0.5159 | 0.3372 |
| MIMIC_NB/NORMAL | KEM | 2.3991 | +1.1889 | -0.0115 | 0.1508 |
| MIMIC_NB/NORMAL | VIN | 1.2947 | +1.3028 | -0.2424 | 0.2522 |

## 六、Q13 BH-FDR（16 组 DeLong）

| 比较 | p | q (BH) | FDR 显著 |
|---|---|---|---|
| CHEX:PNEUMONIA_NIH_vs_KEM | 1.898e-13 | 3.038e-12 | ✅ |
| CHEX:NORMAL_NIH_vs_KEM | 1.096e-12 | 8.766e-12 | ✅ |
| NIH:NORMAL_NIH_vs_KEM | 5.090e-06 | 2.508e-05 | ✅ |
| CHEX:PNEUMONIA_NIH_vs_VIN | 6.269e-06 | 2.508e-05 | ✅ |
| MIMIC_CH:NORMAL_NIH_vs_KEM | 3.381e-05 | 1.082e-04 | ✅ |
| MIMIC_NB:NORMAL_NIH_vs_KEM | 1.198e-04 | 3.194e-04 | ✅ |
| CHEX:NORMAL_NIH_vs_VIN | 3.334e-04 | 7.620e-04 | ✅ |
| NIH:PNEUMONIA_NIH_vs_KEM | 7.654e-02 | 1.397e-01 | — |
| MIMIC_CH:NORMAL_NIH_vs_VIN | 7.907e-02 | 1.397e-01 | — |
| MIMIC_NB:PNEUMONIA_NIH_vs_VIN | 8.733e-02 | 1.397e-01 | — |
| MIMIC_NB:NORMAL_NIH_vs_VIN | 1.409e-01 | 2.050e-01 | — |
| MIMIC_CH:PNEUMONIA_NIH_vs_KEM | 1.624e-01 | 2.166e-01 | — |
| NIH:NORMAL_NIH_vs_VIN | 2.044e-01 | 2.516e-01 | — |
| MIMIC_NB:PNEUMONIA_NIH_vs_KEM | 3.014e-01 | 3.444e-01 | — |
| MIMIC_CH:PNEUMONIA_NIH_vs_VIN | 3.401e-01 | 3.628e-01 | — |
| NIH:PNEUMONIA_NIH_vs_VIN | 6.207e-01 | 6.207e-01 | — |
