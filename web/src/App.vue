<template>
  <n-config-provider :locale="zhCN" :date-locale="dateZhCN" :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <router-view />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { zhCN, dateZhCN, type GlobalThemeOverrides } from 'naive-ui'

const fontFamily =
  "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif"

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#2f6bff',
    primaryColorHover: '#4a82ff',
    primaryColorPressed: '#1f55dc',
    primaryColorSuppl: '#4a82ff',
    successColor: '#18a058',
    warningColor: '#f0a020',
    errorColor: '#e5484d',
    borderRadius: '8px',
    borderRadiusSmall: '6px',
    fontFamily,
    fontSize: '14px',
    fontWeightStrong: '600',
    textColor1: '#0f172a',
    textColor2: '#334155',
    textColor3: '#94a3b8',
    borderColor: '#e5e9f2',
    dividerColor: '#eef1f7',
    bodyColor: '#f3f5fa',
    cardColor: '#ffffff',
    modalColor: '#ffffff',
    popoverColor: '#ffffff',
    tableColor: '#ffffff',
    tableHeaderColor: '#f7f9fc',
    inputColor: '#ffffff',
    hoverColor: '#f4f7fd',
    tagColor: '#f5f7fb',
    actionColor: '#f7f9fc',
    scrollbarColor: 'rgba(148, 163, 184, 0.4)',
    scrollbarColorHover: 'rgba(100, 116, 139, 0.55)',
    boxShadow1: '0 1px 2px rgba(15, 23, 42, 0.06)',
    boxShadow2: '0 8px 24px -12px rgba(15, 23, 42, 0.24)',
    boxShadow3: '0 18px 48px -24px rgba(15, 23, 42, 0.45)',
  },
  Button: {
    borderRadiusTiny: '6px',
    borderRadiusSmall: '7px',
    borderRadiusMedium: '8px',
    borderRadiusLarge: '10px',
    fontWeight: '500',
  },
  Card: {
    borderRadius: '16px',
    borderColor: '#e9edf5',
  },
  DataTable: {
    thColor: '#f6f9fe',
    thTextColor: '#475569',
    thFontWeight: '600',
    tdColorHover: '#f6f9ff',
    borderColor: '#eef1f7',
    borderRadius: '10px',
  },
  Input: {
    borderRadius: '8px',
  },
  Tag: {
    borderRadius: '6px',
  },
  Tabs: {
    tabFontWeightActive: '600',
    barColor: '#2f6bff',
  },
}
</script>
