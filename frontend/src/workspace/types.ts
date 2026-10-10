export type Mode = 'SIMULATION' | 'REAL' | 'REPLAY';
export type Quality = 'VALID' | 'MISSING' | 'STALE' | 'OUT_OF_RANGE' | 'SENSOR_FAULT' | 'SUSPECT';
export interface Signal { value: number | null; unit: string; quality: Quality }
export interface Fault { code: string; name: string; severity: string; score: number | null; probability: number | null; evidence: Record<string, unknown>; action: string; affectedSubsystems: string[]; uncertainty: string; source: 'BACKEND_DIAGNOSTIC' | 'ASSESSMENT_ALERT' | 'LOCAL_DEMO' }
export interface Frame { timestamp: string; engineId: string; missionId: string; phase: string; source: string; signals: Record<string, Signal>; health: number | null; rul: number | null; anomaly: number | null; faults: Fault[]; subsystems: Record<string, number>; advisory: string; synchronized: boolean; sequence?: number }
export interface Controls { throttle: number; load: number; altitude: number; temperature: number; scenario: string; duration: number; seed: number }
export interface SimulationRequest { profile: string; duration_minutes: number; interval_seconds: number; engine_id: string; seed: number; degradation_scenario: string; degradation_severity: number }
export interface Mission { id: string; source: string; frames: Frame[]; configuration?: Controls }
export interface Snapshot { mode: Mode; frame: Frame | null; history: Frame[]; recording: Frame[]; playing: boolean; speed: number; seconds: number; cursor: number; controls: Controls; status: string; error: string; engineId: string; connected: boolean }
