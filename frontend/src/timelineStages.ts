import type { RunStage, StageStatus } from './api'

type TimelineStage = Pick<RunStage, 'status' | 'duration_ms' | 'payload'>

const workflowStageKeys: Record<string, string[]> = {
  input_validator: ['product_preparation'],
  product_normalizer: ['image_understanding', 'peer_matching', 'rag_preparation'],
  statistics_provider: ['statistics'],
  persist_and_export: ['report_export'],
}

function stageDuration(stage: TimelineStage) {
  if (typeof stage.duration_ms === 'number') return stage.duration_ms
  const payloadDuration = stage.payload.duration_ms
  return typeof payloadDuration === 'number' ? payloadDuration : null
}

export function summarizeTimelineStage(
  workflowNodeName: string,
  stagesByKey: ReadonlyMap<string, TimelineStage>,
): { status: StageStatus; duration_ms: number | null } {
  const stages = (workflowStageKeys[workflowNodeName] || [workflowNodeName])
    .map((stageKey) => stagesByKey.get(stageKey))
    .filter((stage): stage is TimelineStage => stage !== undefined)

  if (stages.length === 0) return { status: 'pending', duration_ms: null }
  if (stages.some((stage) => stage.status === 'failed')) return { status: 'failed', duration_ms: null }
  if (stages.some((stage) => stage.status === 'running')) return { status: 'running', duration_ms: null }
  if (stages.some((stage) => stage.status === 'pending')) return { status: 'pending', duration_ms: null }

  const durations = stages.map(stageDuration)
  return {
    status: stages.every((stage) => stage.status === 'skipped') ? 'skipped' : 'succeeded',
    duration_ms: durations.every((duration) => duration !== null)
      ? durations.reduce((total, duration) => total + (duration || 0), 0)
      : null,
  }
}
