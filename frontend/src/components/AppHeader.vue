<template>
  <header class="top">
    <div class="brand">
      <span class="glyph">諦</span>
      <span class="name">谛观 GreenwashGuard</span>
      <span class="sub">企业漂绿风险监测</span>
    </div>
  </header>
</template>

<style scoped>
header.top {
  position: sticky;
  top: 0;
  z-index: 20;
  background: linear-gradient(180deg, var(--ink) 82%, transparent);
  padding: 22px 0 14px;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  border-bottom: 1px solid var(--line-soft);
  margin-bottom: 28px;
}

.brand {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.brand .glyph {
  font-family: 'Noto Serif SC';
  font-weight: 900;
  font-size: 22px;
  color: var(--gold);
  letter-spacing: 2px;
}

.brand .name {
  font-family: 'Noto Serif SC';
  font-weight: 700;
  font-size: 19px;
  letter-spacing: 1px;
}

.brand .sub {
  font-size: 11px;
  color: var(--paper-soft);
  letter-spacing: 2px;
  margin-left: 2px;
}
</style>