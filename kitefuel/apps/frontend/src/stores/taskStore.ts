import { defineStore } from 'pinia'
import {
  useApi,
  type TaskSummary,
  type TaskDetail,
} from '../composables/useApi'

interface TaskStoreState {
  tasks: TaskSummary[]
  selectedTaskId: string | null
  selectedTask: TaskDetail | null
  loading: boolean
  error: string | null
}

export const useTaskStore = defineStore('tasks', {
  state: (): TaskStoreState => ({
    tasks: [],
    selectedTaskId: null,
    selectedTask: null,
    loading: false,
    error: null,
  }),

  actions: {
    async fetchTasks() {
      const api = useApi()
      this.loading = true
      this.error = null
      try {
        const data = await api.getTasks()
        this.tasks = data.tasks
      } catch (err: unknown) {
        this.error = err instanceof Error ? err.message : 'Failed to load tasks'
      } finally {
        this.loading = false
      }
    },

    async fetchTask(id: string) {
      const api = useApi()
      this.loading = true
      this.error = null
      try {
        this.selectedTask = await api.getTask(id)
      } catch (err: unknown) {
        this.error = err instanceof Error ? err.message : `Failed to load task ${id}`
      } finally {
        this.loading = false
      }
    },

    async selectTask(id: string) {
      this.selectedTaskId = id
      await this.fetchTask(id)
    },

    async runAction(id: string, action: string) {
      const api = useApi()
      this.loading = true
      this.error = null
      try {
        await api.postAction(id, action)
        await Promise.all([this.fetchTasks(), this.fetchTask(id)])
      } catch (err: unknown) {
        this.error = err instanceof Error ? err.message : `Action '${action}' failed`
      } finally {
        this.loading = false
      }
    },

    async createTask() {
      const api = useApi()
      this.loading = true
      this.error = null
      try {
        const data = await api.createTask()
        const newId = data.task.id
        await this.fetchTasks()
        await this.selectTask(newId)
      } catch (err: unknown) {
        this.error = err instanceof Error ? err.message : 'Failed to create task'
      } finally {
        this.loading = false
      }
    },

    async resetDemo() {
      const api = useApi()
      this.loading = true
      this.error = null
      try {
        await api.resetDemo()
        this.tasks = []
        this.selectedTaskId = null
        this.selectedTask = null
      } catch (err: unknown) {
        this.error = err instanceof Error ? err.message : 'Failed to reset demo'
      } finally {
        this.loading = false
      }
    },
  },
})
