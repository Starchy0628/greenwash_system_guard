<template>
  <section class="block">
    <div class="block-head"><h2>方法说明</h2></div>
    <div class="method-steps">
      <div class="mstep">
        <div class="n">01</div>
        <div class="t">语句切分过滤</div>
        <div class="d">抓取年报MD&A章节，按句切分，关键词预过滤环保相关语句</div>
      </div>
      <div class="mstep">
        <div class="n">02</div>
        <div class="t">三模型集成投票</div>
        <div class="d">DeepSeek-R1、Qwen-3、GLM-4.7 独立判别，多数票确权，分歧样本转人工复核</div>
      </div>
      <div class="mstep">
        <div class="n">03</div>
        <div class="t">语境情感打分</div>
        <div class="d">对描述性陈述做语境感知情感强度测度，而非简单关键词频次统计</div>
      </div>
      <div class="mstep">
        <div class="n">04</div>
        <div class="t">行业基准修正</div>
        <div class="d">语调分数减去行业年度中位数，合成GW指数，剔除行业间披露风格差异。行业样本量不足30家时结果标注"参考"，建议审慎解读。</div>
      </div>
    </div>
    <div class="metrics">
      <div class="metric">
        <div class="v">0.84</div>
        <div class="l">Fleiss' Kappa 三模型一致性</div>
      </div>
      <div class="metric">
        <div class="v">94.22%</div>
        <div class="l">机判 / 人判 吻合率</div>
      </div>
      <div class="metric">
        <div class="v">92万+</div>
        <div class="l">已分析语句数</div>
      </div>
      <div class="metric">
        <div class="v">3600+</div>
        <div class="l">覆盖A股上市公司</div>
      </div>
    </div>
    <div class="formula">
      <div class="formula-title">GW 指数计算公式</div>
      <div class="formula-body">
        GW 指数<sub>(企业i, 年度t)</sub> = Tone<sub>(企业i, 年度t)</sub> − Median<sub>(所属行业, 年度t)</sub>
      </div>
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
.method-steps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 18px;
}
.mstep {
  background: var(--ink-2);
  border: 1px solid var(--line-soft);
  border-radius: var(--radius);
  padding: 14px;
}
.mstep .n {
  font-family: 'Noto Serif SC';
  color: var(--gold);
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 6px;
}
.mstep .t {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
}
.mstep .d {
  font-size: 11.5px;
  color: var(--paper-soft);
  line-height: 1.5;
}
.metrics {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
}
.metric .v {
  font-family: 'Noto Serif SC';
  font-weight: 900;
  font-size: 24px;
  color: var(--gold);
  font-variant-numeric: tabular-nums;
}
.metric .l {
  font-size: 11px;
  color: var(--paper-soft);
  margin-top: 2px;
}
.formula {
  margin-top: 14px;
  padding: 14px;
  background: var(--ink-2);
  border-radius: var(--radius);
}
.formula-title {
  font-size: 12px;
  color: var(--paper-soft);
  margin-bottom: 8px;
}
.formula-body {
  font-family: 'Noto Serif SC';
  font-size: 16px;
  color: var(--paper);
  text-align: center;
  line-height: 2;
}
</style>