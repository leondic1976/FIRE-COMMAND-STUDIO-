import {describe,expect,it} from 'vitest';
import {clock,formatKST,modeLabel,targetLabel,stages} from '../../packages/domain-schemas';
describe('훈련 화면 공통 계약',()=>{
 it.each([[0,'00:00:00'],[61,'00:01:01'],[3661,'01:01:01'],[-2,'00:00:00']])('가상 시각 %i', (input,output)=>expect(clock(input as number)).toBe(output));
 it('부분훈련과 실제/가상 대상을 명시한다',()=>{expect(modeLabel.SOLO).toContain('개인');expect(targetLabel.VIRTUAL_ON_REAL_MAP).toBe('실지도 + 가상 건물');expect(stages.at(-1)).toBe('CLOSED');});
 it('자정을 넘는 UTC 기록을 한국 시각으로 표시한다',()=>{expect(formatKST('2026-11-16T16:00:00Z')).toContain('01:00');expect(formatKST('2026-11-16T16:00:00Z')).toContain('17.');expect(formatKST('invalid')).toBe('시각 미확인');});
});
