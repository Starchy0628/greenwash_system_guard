<template>
  <section class="block">
    <div class="block-head"><h2>风险分级依据</h2></div>
    <div class="rule-bar">
      <div class="seg normal"></div>
      <div class="seg warn"></div>
    </div>
    <div class="rule-legend">
      <span><b>正常</b> · 前 80% 分位</span>
      <span><b>预警</b> · 后 20% 分位</span>
    </div>
    <div class="rule-text">
      全市场企业GW指数按当年分布统一排序，位于风险最高的后20%分位企业标记为「预警」，触发红色印记提示；其余企业均显示为「正常」，不做额外标注。分位阈值随全市场数据分布定期滚动校准，而非固定数值。
    </div>
  </section>
</template>

<style scoped>
.block { margin-bottom: 44px; }
.block-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 14px;
}
.block-head h2 {
  font-family: 'Noto Serif SC';
  font-weight: 700;
  font-size: 18px;
  margin: 0;
}
.rule-bar {
  display: flex;
  height: 10px;
  border-radius: 6px;
  overflow: hidden;
  margin: 14px 0 10px;
}
.rule-bar .seg.normal {
  background: var(--jade-dim);
  flex: 8;
}
.rule-bar .seg.warn {
  background: var(--cinnabar);
  flex: 2;
}
.rule-legend {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--paper-soft);
}
.rule-legend b { color: var(--paper); }
.rule-text {
  font-size: 13px;
  color: var(--paper-soft);
  line-height: 1.7;
  margin-top: 10px;
}
</style>