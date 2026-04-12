<template>
  <span :class="['inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full', badgeClass]">
    <span v-if="icon">{{ icon }}</span>
    {{ state }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ state: string }>()

interface StateStyle {
  badge: string
  icon: string
}

const STATE_MAP: Record<string, StateStyle> = {
  task_created:     { badge: 'bg-gray-700 text-gray-300',     icon: '' },
  credit_requested: { badge: 'bg-yellow-900 text-yellow-300', icon: '⚡' },
  credit_approved:  { badge: 'bg-yellow-900 text-yellow-300', icon: '⚡' },
  funds_locked:     { badge: 'bg-blue-900 text-blue-300',     icon: '🔒' },
  data_purchased:   { badge: 'bg-blue-900 text-blue-300',     icon: '🔒' },
  result_generated: { badge: 'bg-purple-900 text-purple-300', icon: '📊' },
  user_paid:        { badge: 'bg-green-900 text-green-300',   icon: '✓' },
  lender_repaid:    { badge: 'bg-green-900 text-green-300',   icon: '✓' },
  task_closed:      { badge: 'bg-green-700 text-green-100',   icon: '✅' },
  task_failed:      { badge: 'bg-red-900 text-red-300',       icon: '✗' },
}

const FALLBACK: StateStyle = { badge: 'bg-gray-800 text-gray-400', icon: '' }

const style = computed<StateStyle>(() => STATE_MAP[props.state] ?? FALLBACK)
const badgeClass = computed(() => style.value.badge)
const icon = computed(() => style.value.icon)
</script>
