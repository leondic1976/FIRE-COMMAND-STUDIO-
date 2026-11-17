export interface Identity {id: string; name: string; role: 'admin'|'facilitator'|'evaluator'|'participant'|'board'|'observer'; organization_id: string; person_id: string|null; synthetic_only?: boolean}
export interface Role {id:string; name:string; tasks:string[]; reports_to:string|null; department:string; authority_limits:string; first_minute:string; output:string; source:string; source_url:string; version:number; critical:boolean}
export interface Person {id:string; display_name:string; available:boolean}
export interface Assignment {id:string; role_id:string; person_id:string; effective_from:string; effective_to:string; shift_id:string; status:'ACTIVE'|'PLANNED'|'ENDED'; backups:string[]}
export interface Source {provider:string; as_of:string; rights:'approved'|'restricted'|'unknown'; confidence:'verified'|'approximate'|'unverified'|'simulated'; classification:'SYNTHETIC'|'INTERNAL'|'PUBLIC'; url:string; reviewer:string}
export interface Building {id:string; name:string; use:string; floors:number; floor_height:number; width:number; depth:number; x:number; z:number; rotation:number; color:string; entrances:string[]; footprint:number[][]; accuracy:'SIMULATED'|'APPROXIMATE'|'VERIFIED'}
export interface Building {basement_floors?:number;roof_style?:'FLAT'|'GABLE'|'SHED';window_style?:'REGULAR'|'NONE';wall_finish?:'CONCRETE'|'BRICK'|'METAL'|'GLASS';floor_outlines?:{floor:number;footprint:number[][]}[]}
export type StateValue = string|number|boolean;
export interface AssetNode {index:number;name:string;bounds:number[][]}
export interface AssetManifest {bounds:number[][];nodes:AssetNode[];triangles:number;texture_pixels:number;width:number;height:number;copyright_notice:string;duration_seconds?:number;frame_rate?:number;has_audio?:boolean;video_codec?:string;processing_tool?:string;processing_manifest_sha256?:string}
export interface AssetMapping {building_id:string;purpose:'MODEL'|'FACADE'|'REFERENCE'|'VIDEO';visibility:'PUBLIC'|'STAFF';photo_face:'NORTH'|'SOUTH'|'EAST'|'WEST';unit_scale:number;rotation_y:number;offset:number[];floor_map:Record<string,number>;object_map:Record<string,string>}
export interface AssetBinding extends AssetMapping {id:string;asset_id:string;sha256:string;kind:'GLB'|'PHOTO'|'VIDEO';mime:string;label:string;source:Source;manifest:AssetManifest;reviewed_at:string}
export interface MediaCue {binding_id:string;feature_id:string;clip_start_seconds:number;clip_end_seconds:number}
export interface EventDefinition {media_cues?:MediaCue[]}
export interface Message {media_cues?:MediaCue[]}
/** Browser-local monotonic receipt instant; never persisted or sent to the API. */
export interface SessionState {received_at_ms?:number;clock_sampled_at?:string}
export interface Subject {asset_bindings?:AssetBinding[]}
/** Match a reviewed model's centre, footprint and orientation in 2D and 3D. */
export function assetDisplayBuilding(subject:Subject,building:Building):Building {
 const model=subject.asset_bindings?.find(binding=>binding.building_id===building.id&&binding.purpose==='MODEL');
 if(!model)return building;
 const angle=(building.rotation+subject.north_rotation)*Math.PI/180,c=Math.cos(angle),s=Math.sin(angle),bounds=model.manifest.bounds;
 return {...building,x:building.x+c*model.offset[0]+s*model.offset[2],z:building.z-s*model.offset[0]+c*model.offset[2],
  width:(bounds[1][0]-bounds[0][0])*model.unit_scale,depth:(bounds[1][2]-bounds[0][2])*model.unit_scale,rotation:building.rotation+model.rotation_y,footprint:[]};
}
export interface ExternalFact {external_id:string;name:string;fields:Record<string,string|number|boolean|null>}
export interface ExternalLayer {id:string;import_id:string;provider:'building_registry'|'weather'|'hydrant';source:Source;retrieved_at:string;raw_sha256:string;records:ExternalFact[];warnings:string[]}
export interface Subject {external_layers?:ExternalLayer[]}
export interface Feature {data_origin?:'SIMULATED'|'REFERENCE';source_layer_id?:string|null}
export interface Feature {id:string; name:string; kind:'ZONE'|'ENTRANCE'|'HYDRANT'|'VEHICLE'|'ROAD'|'PERIMETER'|'ASSEMBLY'|'HOSPITAL'|'PARKING'|'ROOM'|'CORRIDOR'|'STAIR'|'ELEVATOR'|'COMPARTMENT'|'EVAC_ROUTE'|'FIRE_EQUIPMENT'|'HAZMAT'|'PASSAGE'; building_id:string|null; floor:number; x:number; z:number; state:Record<string,StateValue>;width?:number;depth?:number;height?:number;rotation?:number;linked_building_id?:string|null}
export interface Subject {id:string; name:string; target_mode:'VIRTUAL'|'REAL'|'VIRTUAL_ON_REAL_MAP'; scenario_factuality:'SIMULATED'|'HISTORICAL'; map_context:'SYNTHETIC'|'REAL'; latitude:number; longitude:number; north_rotation:number; elevation:number; buildings:Building[]; features:Feature[]; source:Source; model_accuracy:'SIMULATED'|'APPROXIMATE'|'VERIFIED'; interior_verified:boolean}
export interface Patch {feature_id:string; field:string; before:StateValue; after:StateValue; visual_kind:'ILLUSTRATIVE'|'ANNOTATION'}
export interface EventDefinition {id:string; title:string; kind:string; category:string; objective:string; sender:string; recipient_role_ids:string[]; visibility:'PUBLIC'|'PRIVATE'; priority:'NORMAL'|'HIGH'|'CRITICAL'; channel:string; truth_status:string; text:string; expected_actions:string; trigger:{kind:string; at_seconds:number; action:string; condition:Record<string,unknown>; auto_release:boolean}; patches:Patch[]; next_event_ids:string[]; terminal:boolean; simulated_at:number; evaluation_links:string[]; condition_met?:boolean; deferred_until?:number}
export interface Readiness {score:number; acknowledged_version:number; explanation:string; at:string; feedback:{question_id:string; correct:boolean; reason:string}[]; attempts:unknown[]}
export interface Review {approved:boolean; note:string; reviewer_id:string; at:string}
export interface Exercise {id:string; name:string; organization_name:string; objective:string; mode:'GROUP'|'PARTIAL'|'SOLO'|'DIAGNOSTIC'; roles:Role[]; persons:Person[]; assignments:Assignment[]; subject:Subject; events:EventDefinition[]; start_event_id:string; pass_score:number; readiness:Record<string,Readiness>; reviews:Record<string,Review>; published:boolean; revision:number; rehearsal_passed:boolean; organization_approval:string; simulated_roles:string[]}
export interface ExerciseList {id:string; name:string; mode:string; published:boolean; state_version:number; revision:number}
export interface SessionList {id:string; name:string; status:string; mode:string; seq:number; created_at:string}
export interface ActionRecord {event_id:string; role_id:string; person_id:string; stage:string; action_type:string; text:string; visibility:string; truth_status:string; seq:number; at:string; simulated_seconds:number; actor_id:string}
export interface Message {id:string; title:string; sender:string; text:string; recipient_role_ids:string[]; visibility:string; priority:string; channel:string; truth_status:string; at:string; simulated_seconds:number; stages:ActionRecord[]; event_seq:number; reverted?:boolean}
export interface DecisionRecord {summary:string; role_id:string; report_at_seconds:number; event_id:string; visibility:string; at:string; seq:number; actor_id:string}
export interface Observation {id:string; person_id:string; role_id:string; event_id:string; action_seq:number|null; criterion:string; score:number|null; evidence:string; strength:string; improvement:string; uncertainty:string; corrects_id:string|null; at:string}
export interface Improvement {id:string; title:string; owner_role_id:string; due_date:string; observation_id:string; retraining:string; evidence:string; status:string}
export interface Handover {id:string; role_id:string; from_person_id:string; to_person_id:string; status:string; summary?:string; pending_tasks?:string; history:{status:string; at:string; actor_id:string; note?:string}[]}
export interface LogEntry {seq:number; kind:string; actor_id:string; at:string; simulated_seconds:number; payload:Record<string,unknown>; visibility:string; recipient_role_ids:string[]; title?:string}
export interface SessionState {id:string; exercise_id:string; participant_count:number; assignment_count:number; name:string; mode:string; status:string; stage:string; seq:number; state_version:number; elapsed_seconds:number; subject:Subject; scene:Record<string,Record<string,StateValue>>; messages:Message[]; decisions:DecisionRecord[]; roles:Pick<Role,'id'|'name'|'department'>[]; my_role_ids:string[]; watermark:string; created_at:string; timeline:Pick<LogEntry,'seq'|'kind'|'at'|'simulated_seconds'|'title'>[]; candidates?:EventDefinition[]; exercise?:Exercise; roster?:Assignment[]; handovers?:Handover[]; observations?:Observation[]; improvements?:Improvement[]; actions?:ActionRecord[]; log?:LogEntry[]; aar_approval?:{evaluator_id:string; at:string; note:string}|null}
export interface Issue {gate:string; severity:'ERROR'|'WARNING'; message:string}
export interface Exercise {organization_type:'FIELD_COMMAND'|'CONTROL_GROUP'|'COMBINED'|'CUSTOM';practice_owner_person_id?:string|null;practice_difficulty?:string}
export interface SessionState {practice?:{difficulty:string;self_practice:boolean;readiness:string;role:Role;next_candidates:{id:string;condition_met:boolean}[]};practice_feedback?:{event_id:string;text:string;retraining:string;action_seq:number}[]}
export const modeLabel: Record<string,string> = {GROUP:'공동 토론훈련', PARTIAL:'부분 임무훈련', SOLO:'개인 임무연습', DIAGNOSTIC:'진단훈련 · 사전미숙지 허용'};
export const targetLabel: Record<string,string> = {VIRTUAL:'가상 대상물 · 가상 배치',REAL:'실제 대상물 기반 가상 상황훈련',VIRTUAL_ON_REAL_MAP:'실지도 + 가상 건물'};
export const stageLabels: Record<string,string> = {RECEIVED:'수신', ACKNOWLEDGED:'인지', VERIFIED:'사실 확인', REPORTED:'보고·협조', DECIDED:'결정·조치', REPLIED:'회신', CLOSED:'종결'};
export const stages = Object.keys(stageLabels);
export const eventLabels:Record<string,string>={SESSION_STARTED:'훈련 시작',SESSION_PAUSED:'훈련 일시정지',SESSION_RESUMED:'훈련 재개',SESSION_ENDED:'훈련 종료',SESSION_RECOVERED:'중단 후 복구',INJECT_RELEASED:'사건 공개',INJECT_DEFERRED:'사건 연기',INJECT_SKIPPED:'사건 건너뛰기',INJECT_UNDONE:'사건 되돌림',STAGE_TRANSITIONED:'통제단 전환',MESSAGE_RECEIVED:'메시지 수신',MESSAGE_ACKNOWLEDGED:'메시지 인지',MESSAGE_VERIFIED:'사실 확인',MESSAGE_REPORTED:'보고·협조',MESSAGE_DECIDED:'결정·조치',MESSAGE_REPLIED:'회신',MESSAGE_CLOSED:'메시지 종결',DECISION_LOGGED:'지휘결론 기록',HANDOVER_UPDATED:'대체·인계 단계 변경',ROSTER_CHANGED:'현재 담당자 변경',OBSERVATION_RECORDED:'관찰 기록',IMPROVEMENT_ASSIGNED:'개선과제 등록',IMPROVEMENT_COMPLETED:'개선 완료 증거',AAR_APPROVED:'강평 승인',PRACTICE_FEEDBACK:'모의 동료 피드백'};
Object.assign(eventLabels,{SCENE_REVERTED:'장면 되돌림',ORGANIZATION_TRANSITIONED:'통제단 전환',EVENT_DEFER:'사건 연기',EVENT_SKIP:'사건 건너뛰기'});
export const eventLabel=(kind:string)=>eventLabels[kind]||kind;
export function clock(seconds:number) {const s=Math.max(0,Math.floor(seconds));return `${String(Math.floor(s/3600)).padStart(2,'0')}:${String(Math.floor(s/60)%60).padStart(2,'0')}:${String(s%60).padStart(2,'0')}`;}
export function formatKST(value:string){const date=new Date(value);return Number.isNaN(date.valueOf())?'시각 미확인':new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',dateStyle:'short',timeStyle:'short',hour12:false}).format(date)+' KST';}
/** A deliberate empty selection while creating a new exercise must remain empty. */
export function chooseInitialSession(current:string,sessions:Pick<SessionList,'id'>[],initialized:boolean){return current||(!initialized?sessions.at(-1)?.id||'':'');}
