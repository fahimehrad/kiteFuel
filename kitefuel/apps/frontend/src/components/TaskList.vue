<template>
  <div class="flex flex-col h-full">

    <!-- Header / Create button -->
    <div class="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
      <span class="text-xs text-gray-500">{{ store.tasks.length }} task{{ store.tasks.length !== 1 ? 's' : '' }}</span>
      <button
        @click="store.createTask()"
        :disabled="store.loading"
        class="text-xs bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white px-3 py-1 rounded-md transition"
      >
        + Create Demo Task
      </button>
    </div>

    <!-- Task rows -->
    <div class="flex-1 overflow-y-auto px-3 py-2 space-y-1.5">
      <div
        v-if="store.tasks.length === 0 && !store.loading"
        class="text-gray-600 text-xs text-center mt-8"
      >
        No tasks yet.
      </div>

      <button
        v-for="task in store.tasks"
        :key="task.id"
        @click="store.selectTask(task.id)"
        :class="[
          'w-full text-left px-3 py-2.5 rounded-lg border transition',
          store.selectedTaskId === task.id
            ? 'bg-purple-900/40 border-purple-600'
            : 'bg-gray-800 border-gray-700 hover:border-gray-600',
        ]"
      >
        <!-- Task ID (shortened) -->
        <div class="font-mono text-xs text-gray-500 truncate mb-1">
          {{ task.id.slice(0, 8) }}…
        </div>

        <!-- State badge + date -->
        <div class="flex items-center justify-between gap-2">
          <StateBadge :state="task.state" />
          <span class="text-xs text-gray-600 shrink-0">{{ formatDate(task.created_at) }}</span>
        </div>
      </button>
    </div>

  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useTaskStore } from '../stores/taskStore'
import StateBadge from './StateBadge.vue'

const store = useTaskStore()

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

let pollInterval: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  store.fetchTasks()
  pollInterval = setInterval(() => {
    store.fetchTasks()
  }, 3000)
})

onUnmounted(() => {
  if (pollInterval !== null) {
    clearInterval(pollInterval)
    pollInterval = null
  }
})
</script>
