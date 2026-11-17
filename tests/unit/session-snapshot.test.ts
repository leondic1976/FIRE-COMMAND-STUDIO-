import {describe,it,expect} from 'vitest';
import {latestSnapshot} from '../../packages/domain-schemas/session-snapshot';
describe('REST/WS 훈련 스냅샷 순서',()=>{
 const current={id:'session-synthetic',state_version:4,clock_sampled_at:'2026-11-17T03:00:02Z'};
 it('늦게 받은 이전 사건 버전으로 화면을 되돌리지 않는다',()=>expect(latestSnapshot(current,{...current,state_version:3,clock_sampled_at:'2026-11-17T03:00:03Z'})).toBe(current));
 it('같은 버전의 오래된 시계 표본도 최신 표본을 덮어쓰지 않는다',()=>expect(latestSnapshot(current,{...current,clock_sampled_at:'2026-11-17T03:00:01Z'})).toBe(current));
 it('새 버전은 이전 시각 표본이 있더라도 서버 버전 순서로 적용한다',()=>{const next={...current,state_version:5,clock_sampled_at:'2026-11-17T03:00:00Z'};expect(latestSnapshot(current,next)).toBe(next);});
 it('최초/다른 실행본은 그 실행본의 버전을 독립적으로 적용한다',()=>{const next={...current,id:'other',state_version:1};expect(latestSnapshot(current,next)).toBe(next);expect(latestSnapshot(null,next)).toBe(next);});
});
