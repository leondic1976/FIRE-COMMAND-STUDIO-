import type { Exercise, Message, SessionState, Subject } from '../../../packages/domain-schemas';

/** A browser workspace and a hosted identity boundary have different guarantees. */
export type RuntimeMode = 'browser' | 'hosted';
export interface RuntimeCapabilities {
  mode: RuntimeMode;
  persistence: 'browser' | 'server';
  serverEnforcedIdentity: boolean;
  nativeProcessingApproved: boolean;
  externalSecretsSupported: boolean;
}
export interface VersionedCommand<T = unknown> {
  id: string;
  expectedVersion: number;
  operation: string;
  payload: T;
}
export interface Committed<T> {
  commandId: string;
  version: number;
  sequence: number;
  value: T;
}
/** Projection is deliberately separate from the private SessionState type. */
export interface PublicDisplaySnapshot {
  schemaVersion: 1;
  sessionId: string;
  version: number;
  sequence: number;
  watermark: '훈련용 · 가상 시각효과';
  subject: Pick<Subject, 'id' | 'name' | 'target_mode' | 'scenario_factuality' | 'map_context' | 'latitude' | 'longitude' | 'north_rotation' | 'elevation' | 'buildings' | 'features' | 'model_accuracy' | 'interior_verified'>;
  scene: SessionState['scene'];
  messages: Pick<Message, 'id' | 'title' | 'sender' | 'text' | 'priority' | 'channel' | 'truth_status' | 'simulated_seconds'>[];
  elapsedSeconds: number;
  status: string;
}
export interface TrainingRuntime {
  readonly capabilities: RuntimeCapabilities;
  initialize(): Promise<void>;
  listExercises(): Promise<Pick<Exercise, 'id' | 'name' | 'published' | 'revision'>[]>;
  execute<T>(sessionId: string, command: VersionedCommand): Promise<Committed<T>>;
  publicSnapshot(sessionId: string): Promise<PublicDisplaySnapshot>;
  exportBackup(): Promise<Blob>;
  restoreBackup(backup: Blob): Promise<void>;
  close(): Promise<void>;
}
