# 多模型结果汇总（自动生成 · 2026-11-09）

模型：NIH, CHEX, MIMIC_CH, MIMIC_NB

## 一、判别能力（AUC）与校准（ECE）

### NIH

| 标签 | 数据集 | n | 先验 | AUC | ECE(10箱) |
|---|---|---|---|---|---|
| PNEUMONIA | NIH | 2819 | 2.3% | 0.7229 | 0.2389 |
| PNEUMONIA | KEM | 5828 | 72.9% | 0.7834 | 0.2925 |
| PNEUMONIA | VIN | 702 | 38.7% | 0.7036 | 0.0888 |
| NORMAL | NIH | 2819 | 97.7% | 0.7618 | 0.4359 |
| NORMAL | KEM | 5828 | 27.1% | 0.9078 | 0.1849 |
| NORMAL | VIN | 702 | 61.3% | 0.8071 | 0.1580 |

### CHEX

| 标签 | 数据集 | n | 先验 | AUC | ECE(10箱) |
|---|---|---|---|---|---|
| PNEUMONIA | NIH | 2819 | 2.3% | 0.7345 | 0.2057 |
| PNEUMONIA | KEM | 5828 | 72.9% | 0.9556 | 0.2035 |
| PNEUMONIA | VIN | 702 | 38.7% | 0.8820 | 0.1590 |
| NORMAL | NIH | 2819 | 97.7% | 0.7420 | 0.4736 |
| NORMAL | KEM | 5828 | 27.1% | 0.9594 | 0.1141 |
| NORMAL | VIN | 702 | 61.3% | 0.8625 | 0.1068 |

### MIMIC_CH

| 标签 | 数据集 | n | 先验 | AUC | ECE(10箱) |
|---|---|---|---|---|---|
| PNEUMONIA | NIH | 2819 | 2.3% | 0.6687 | 0.3085 |
| PNEUMONIA | KEM | 5828 | 72.9% | 0.6162 | 0.2065 |
| PNEUMONIA | VIN | 702 | 38.7% | 0.7082 | 0.0612 |
| NORMAL | NIH | 2819 | 97.7% | 0.6777 | 0.5174 |
| NORMAL | KEM | 5828 | 27.1% | 0.8153 | 0.1031 |
| NORMAL | VIN | 702 | 61.3% | 0.7443 | 0.2159 |

### MIMIC_NB

| 标签 | 数据集 | n | 先验 | AUC | ECE(10箱) |
|---|---|---|---|---|---|
| PNEUMONIA | NIH | 2819 | 2.3% | 0.6917 | 0.3758 |
| PNEUMONIA | KEM | 5828 | 72.9% | 0.7282 | 0.1983 |
| PNEUMONIA | VIN | 702 | 38.7% | 0.7594 | 0.1832 |
| NORMAL | NIH | 2819 | 97.7% | 0.7192 | 0.5159 |
| NORMAL | KEM | 5828 | 27.1% | 0.8467 | 0.0958 |
| NORMAL | VIN | 702 | 61.3% | 0.7743 | 0.2424 |

## 二、先验匹配：跨度收缩与排序

| 模型 | 标签 | 原始跨度 | 匹配后跨度 | 保留 | 原始排序 | 匹配后排序 | 翻转 |
|---|---|---|---|---|---|---|---|
| NIH | PNEUMONIA | 3.294× | 1.673× | 50.8% | VIN < NIH < KEM | KEM < VIN < NIH | 是 |
| NIH | NORMAL | 2.760× | 1.366× | 49.5% | VIN < KEM < NIH | NIH < VIN < KEM | 是 |
| CHEX | PNEUMONIA | 1.293× | 1.452× | 112.2% | VIN < KEM < NIH | KEM < VIN < NIH | 是 |
| CHEX | NORMAL | 4.437× | 2.216× | 50.0% | VIN < KEM < NIH | VIN < NIH < KEM | 是 |
| MIMIC_CH | PNEUMONIA | 5.043× | 1.967× | 39.0% | VIN < KEM < NIH | VIN < NIH < KEM | 是 |
| MIMIC_CH | NORMAL | 5.018× | 1.385× | 27.6% | KEM < VIN < NIH | VIN < NIH < KEM | 是 |
| MIMIC_NB | PNEUMONIA | 2.052× | 1.591× | 77.5% | VIN < KEM < NIH | NIH < KEM < VIN | 是 |
| MIMIC_NB | NORMAL | 5.387× | 1.295× | 24.0% | KEM < VIN < NIH | NIH < VIN < KEM | 是 |

## 三、排序翻转的符号检验（方向一致性）

| 模型 | 标签 | 完全翻转 | 方向一致性 | p 值 | 最优者改变 | p 值 | 判定 |
|---|---|---|---|---|---|---|---|
| NIH | PNEUMONIA | 436/488 | 89.3% | 1.32e-76 | 448/500 | 1.22e-79 | flip_not_confirmed |
| NIH | NORMAL | 274/487 | 56.3% | 0.00649 | 274/500 | 0.0355 | flip_not_confirmed |
| CHEX | PNEUMONIA | 242/493 | 49.1% | 0.719 | 493/500 | 9.21e-136 | systematic_flip_confirmed |
| CHEX | NORMAL | 0/491 | 0.0% | 3.13e-148 | 0/500 | 6.11e-151 | flip_not_confirmed |
| MIMIC_CH | PNEUMONIA | 60/415 | 14.5% | 4.66e-52 | 61/500 | 1.33e-71 | flip_not_confirmed |
| MIMIC_CH | NORMAL | 500/500 | 100.0% | 6.11e-151 | 500/500 | 6.11e-151 | flip_not_confirmed |
| MIMIC_NB | PNEUMONIA | 495/499 | 99.2% | 3.14e-141 | 498/500 | 7.65e-146 | systematic_flip_confirmed |
| MIMIC_NB | NORMAL | 500/500 | 100.0% | 6.11e-151 | 500/500 | 6.11e-151 | flip_not_confirmed |

## 四、DCA 阈值翻转

| 模型 | 标签 | 翻转阈值数 |
|---|---|---|
| NIH | PNEUMONIA | 1/3 |
| NIH | NORMAL | 2/3 |
| CHEX | PNEUMONIA | 0/3 |
| CHEX | NORMAL | 3/3 |
| MIMIC_CH | PNEUMONIA | 3/3 |
| MIMIC_CH | NORMAL | 2/3 |
| MIMIC_NB | PNEUMONIA | 2/3 |
| MIMIC_NB | NORMAL | 2/3 |

## 五、跨模型一致性（本研究的核心判据）

**⚠️ 部分组合未确认系统性翻转**（2/8 成立）：
  - CHEX / PNEUMONIA: p=0.719
  - MIMIC_NB / PNEUMONIA: p=3.14e-141
  → 必须在 Discussion 中如实交代哪些模型成立、哪些不成立。
