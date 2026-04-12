<template>
  <div class="min-h-screen bg-gray-950 text-gray-100 flex flex-col">

    <!-- Navbar -->
    <nav class="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center gap-4">
      <span class="text-xl font-bold text-white tracking-tight">KiteFuel</span>
      <span class="text-xs font-medium bg-purple-700 text-purple-100 px-2 py-0.5 rounded-full">
        Built on Kite
      </span>
    </nav>

    <!-- Error banner -->
    <div v-if="store.error" class="bg-red-900/60 border-b border-red-700 px-6 py-2 text-red-200 text-sm">
      ⚠ {{ store.error }}
    </div>

    <!-- Loading indicator -->
    <div v-if="store.loading" class="h-0.5 bg-purple-600 animate-pulse w-full" />

    <!-- Main layout -->
    <main class="flex flex-1 overflow-hidden">

      <!-- Left column — Task list (30%) -->
      <aside class="w-[30%] border-r border-gray-800 bg-gray-900 flex flex-col">
        <div class="px-5 py-4 border-b border-gray-800">
          <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wider">Tasks</h2>
        </div>
        <div class="flex-1 overflow-hidden">
          <TaskList />
        </div>
      </aside>

      <!-- Right column — Task Detail (70%) -->
      <section class="flex-1 flex flex-col bg-gray-950 overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-800">
          <h2 class="text-sm font-semibold text-gray-400 uppercase tracking-wider">Task Detail</h2>
        </div>
        <div class="flex flex-1 overflow-hidden">
          <TaskDetail />
        </div>
      </section>

    </main>
  </div>
</template>

<script setup lang="ts">
import { useTaskStore } from './stores/taskStore'
import TaskList from './components/TaskList.vue'
import TaskDetail from './components/TaskDetail.vue'

const store = useTaskStore()
</script>
