# 多模型结果汇总（自动生成 · 2026-11-09）

模型：NIH, CHEX, MIMIC_CH, MIMIC_NB

## 一、判别能力（AUC）与校准（ECE）

### NIH

| 标签 | 数据集 | n | 先验 | AUC | ECE(10箱) |
|---|---|---|---|---|---|
| PNEUMONIA | NIH | 2819 | 2.3% | 0.7229 | 0.2389 |
| PNEUMONIA | KEM | 5824 | 72.9% | 0.7832 | 0.2927 |
| PNEUMONIA | VIN | 702 | 38.7% | 0.7036 | 0.0888 |
| NORMAL | NIH | 2819 | 97.7% | 0.7618 | 0.4359 |
| NORMAL | KEM | 5824 | 27.1% | 0.9077 | 0.1850 |
| NORMAL | VIN | 702 | 61.3% | 0.8071 | 0.1580 |

### CHEX

| 标签 | 数据集 | n | 先验 | AUC | ECE(10箱) |
|---|---|---|---|---|---|
| PNEUMONIA | NIH | 2819 | 2.3% | 0.7345 | 0.2057 |
| PNEUMONIA | KEM | 5824 | 72.9% | 0.9555 | 0.2036 |
| PNEUMONIA | VIN | 702 | 38.7% | 0.8820 | 0.1590 |
| NORMAL | NIH | 2819 | 97.7% | 0.7420 | 0.4736 |
| NORMAL | KEM | 5824 | 27.1% | 0.9594 | 0.1140 |
| NORMAL | VIN | 702 | 61.3% | 0.8625 | 0.1068 |

### MIMIC_CH

| 标签 | 数据集 | n | 先验 | AUC | ECE(10箱) |
|---|---|---|---|---|---|
| PNEUMONIA | NIH | 2819 | 2.3% | 0.6687 | 0.3085 |
| PNEUMONIA | KEM | 5824 | 72.9% | 0.6166 | 0.2066 |
| PNEUMONIA | VIN | 702 | 38.7% | 0.7082 | 0.0612 |
| NORMAL | NIH | 2819 | 97.7% | 0.6777 | 0.5174 |
| NORMAL | KEM | 5824 | 27.1% | 0.8153 | 0.1031 |
| NORMAL | VIN | 702 | 61.3% | 0.7443 | 0.2159 |

### MIMIC_NB

| 标签 | 数据集 | n | 先验 | AUC | ECE(10箱) |
|---|---|---|---|---|---|
| PNEUMONIA | NIH | 2819 | 2.3% | 0.6917 | 0.3758 |
| PNEUMONIA | KEM | 5824 | 72.9% | 0.7284 | 0.1985 |
| PNEUMONIA | VIN | 702 | 38.7% | 0.7594 | 0.1832 |
| NORMAL | NIH | 2819 | 97.7% | 0.7192 | 0.5159 |
| NORMAL | KEM | 5824 | 27.1% | 0.8465 | 0.0956 |
| NORMAL | VIN | 702 | 61.3% | 0.7743 | 0.2424 |

## 二、先验匹配：跨度收缩与排序

| 模型 | 标签 | 原始跨度 | 匹配后跨度 | 保留 | 原始排序 | 匹配后排序 | 翻转 |
|---|---|---|---|---|---|---|---|
| NIH | PNEUMONIA | 3.295× | 1.675× | 50.8% | VIN < NIH < KEM | KEM < VIN < NIH | 是 |
| NIH | NORMAL | 2.760× | 1.364× | 49.4% | VIN < KEM < NIH | NIH < VIN < KEM | 是 |
| CHEX | PNEUMONIA | 1.293× | 1.475× | 114.0% | VIN < KEM < NIH | KEM < VIN < NIH | 是 |
| CHEX | NORMAL | 4.437× | 2.206× | 49.7% | VIN < KEM < NIH | VIN < NIH < KEM | 是 |
| MIMIC_CH | PNEUMONIA | 5.043× | 1.974× | 39.1% | VIN < KEM < NIH | VIN < NIH < KEM | 是 |
| MIMIC_CH | NORMAL | 5.017× | 1.384× | 27.6% | KEM < VIN < NIH | VIN < NIH < KEM | 是 |
| MIMIC_NB | PNEUMONIA | 2.052× | 1.591× | 77.5% | VIN < KEM < NIH | NIH < KEM < VIN | 是 |
| MIMIC_NB | NORMAL | 5.398× | 1.291× | 23.9% | KEM < VIN < NIH | NIH < VIN < KEM | 是 |

## 三、排序翻转的符号检验（方向一致性）

| 模型 | 标签 | 完全翻转 | 方向一致性 | p 值 | 最优者改变 | p 值 | 判定 |
|---|---|---|---|---|---|---|---|
| NIH | PNEUMONIA | 435/485 | 89.7% | 1.05e-77 | 447/500 | 1.03e-78 | flip_not_confirmed |
| NIH | NORMAL | 274/493 | 55.6% | 0.0149 | 276/500 | 0.0225 | flip_not_confirmed |
| CHEX | PNEUMONIA | 242/495 | 48.9% | 0.653 | 495/500 | 1.58e-139 | systematic_flip_confirmed |
| CHEX | NORMAL | 0/489 | 0.0% | 1.25e-147 | 0/500 | 6.11e-151 | flip_not_confirmed |
| MIMIC_CH | PNEUMONIA | 60/411 | 14.6% | 3.99e-51 | 60/500 | 1.84e-72 | flip_not_confirmed |
| MIMIC_CH | NORMAL | 500/500 | 100.0% | 6.11e-151 | 500/500 | 6.11e-151 | flip_not_confirmed |
| MIMIC_NB | PNEUMONIA | 495/498 | 99.4% | 5.03e-143 | 497/500 | 1.27e-143 | systematic_flip_confirmed |
| MIMIC_NB | NORMAL | 499/500 | 99.8% | 3.06e-148 | 500/500 | 6.11e-151 | flip_not_confirmed |

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
  - CHEX / PNEUMONIA: p=0.653
  - MIMIC_NB / PNEUMONIA: p=5.03e-143
  → 必须在 Discussion 中如实交代哪些模型成立、哪些不成立。
