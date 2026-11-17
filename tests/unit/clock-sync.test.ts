import {describe,it,expect} from 'vitest';
import {trainingSeconds} from '../../packages/domain-schemas/clock-sync';
describe('서버 훈련시계 보정',()=>{
 const snapshot={elapsed_seconds:7,status:'RUNNING',clock_sampled_at:'2026-11-17T03:00:00.000Z',received_at_ms:3000};
 const sample={serverMs:Date.parse(snapshot.clock_sampled_at),localMidpointMs:1000,roundTripMs:10};
 it('클라이언트 절대시계와 지연 수신시각 대신 서버 표본과 단조시계를 사용한다',()=>expect(trainingSeconds(snapshot,sample,5000)).toBe(11));
 it('서로 다른 브라우저의 시간 원점과 렌더/수신 지연에도 같은 훈련시각을 산출한다',()=>{const other={...sample,localMidpointMs:9000};expect(trainingSeconds({...snapshot,received_at_ms:12000},other,13000)).toBe(trainingSeconds(snapshot,sample,5000));});
 it('일시정지/과거 재생은 보정된 현재시각이 흘러도 정지한다',()=>{expect(trainingSeconds({...snapshot,status:'PAUSED'},sample,90000)).toBe(7);expect(trainingSeconds({...snapshot,status:'REPLAY'},sample,90000)).toBe(7);});
 it('보정 전에는 수신시각 대안을 사용하고 음수 지연을 더하지 않는다',()=>{expect(trainingSeconds(snapshot,null,5000)).toBe(9);expect(trainingSeconds(snapshot,sample,500)).toBe(7);});
});
