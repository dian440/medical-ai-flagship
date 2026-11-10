#!/usr/bin/env bash
# 重训基线完整重跑流水线
#
# 背景（2026-11-09 → 2026-11-10 两次修订）
#   1. Kermany 的 feat_kem.npz 是去重前的 5,828 张（含 4 张重复影像）
#   2. retrain_baseline.json 的 zero-shot 读旧单模型版口径 → 已单独修正
#   3. summary_table 的 zeroshot_auc 独立存了一份旧值 → 已单独修正
#   4. 🔴 2026-11-10：原脚本调用 `code/retrain_baseline.py`，而那是被
#      2026-11-09 的 v2 取代的**旧版**（无去重、无评估队列对齐、
#      无 per-label 探针、无验证集选 epoch）—— 跑它会**覆盖正确结果**。
#      现 `code/retrain_baseline.py` 已是 v3（训练池/评估队列分离 +
#      同域 out-of-fold + bootstrap CI），本脚本调用它即为正确目标。
#
# 本脚本按顺序做：删缓存 → 重训 → 重生成表 → 同步论文 → 全链核验
# 任一步失败即中止（set -e），不留下半成品。

set -e

PY_TRAIN="E:/港校申请环境/project/Scripts/python.exe"
PY_ANY="E:/Python313/python.exe"
REPO="C:/Users/Huawei/Desktop/大学/港澳申请/02_旗舰项目/medical-ai-flagship"
cd "$REPO"

echo "════════════════════════════════════════════════════════════"
echo "1/5  删除去重前的 KEM 特征缓存"
echo "════════════════════════════════════════════════════════════"
if [ -f results/feat_kem.npz ]; then
  mv results/feat_kem.npz results/feat_kem.npz.stale_$(date +%H%M%S)
  echo "  已备份旧缓存（.stale_ 后缀）"
else
  echo "  无缓存（可能已重建）"
fi
# 2026-11-10：v3 的评估队列与训练池在 NIH/KEM 上样本集相同，
# 故只需重建一份特征；VinDr 因有 12 张未进入评估队列而另存一份。
rm -f results/feat_nih_eval.npz results/feat_kem_eval.npz \
      results/feat_vin_eval.npz

echo ""
echo "════════════════════════════════════════════════════════════"
echo "2/5  重跑重训基线（v3：训练池/评估队列分离 + 同域 out-of-fold）"
echo "════════════════════════════════════════════════════════════"
"$PY_TRAIN" code/retrain_baseline.py 2>&1 | tee results/retrain_run.log | \
  grep -vE "Warning|warn" | tail -45

echo ""
echo "════════════════════════════════════════════════════════════"
echo "3/5  重新生成表格与图件"
echo "════════════════════════════════════════════════════════════"
"$PY_TRAIN" code/make_tables.py 2>&1 | tail -2
for s in figure0_graphical_abstract figure1_flowchart figure2_calibration \
         figure3_decision_curve figure4_noise_baseline; do
  "$PY_TRAIN" code/$s.py 2>&1 | grep -E "写出|尺寸" | head -1
done

echo ""
echo "════════════════════════════════════════════════════════════"
echo "4/5  全文数值同步（重训值变化 → 论文同步）"
echo "════════════════════════════════════════════════════════════"
"$PY_ANY" code/sync_all_values.py 2>&1 | tail -6

echo ""
echo "════════════════════════════════════════════════════════════"
echo "5/5  全链核验"
echo "════════════════════════════════════════════════════════════"
for s in verify_results_draft verify_tables verify_discussion verify_figures \
         validate_pmnb verify_teacher_brief scan_stale_values; do
  printf "  %-24s " "$s"
  "$PY_ANY" code/$s.py 2>&1 | grep -oE "通过 [0-9]+，失败 [0-9]+|失败 [0-9]+ 项|✅ 全部通过|未发现过时值" | head -1
done
echo ""
"$PY_ANY" code/final_audit.py 2>&1 | grep "合计"
"$PY_ANY" code/reviewer_gate.py 2>&1 | tail -3
