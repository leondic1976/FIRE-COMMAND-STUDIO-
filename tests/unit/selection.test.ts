import {describe,expect,it} from 'vitest';
import {chooseInitialSession} from '../../packages/domain-schemas';
describe('훈련 선택의 의도 보존',()=>{
 it('첫 입장 때 기존 최신 실행본을 제안한다',()=>expect(chooseInitialSession('',[{id:'old-session'}],false)).toBe('old-session'));
 it('새 훈련 제작을 위해 비운 선택에 과거 실행본을 다시 연결하지 않는다',()=>expect(chooseInitialSession('',[{id:'old-session'}],true)).toBe(''));
 it('직접 선택한 새 실행본은 목록 갱신에도 유지한다',()=>expect(chooseInitialSession('new-session',[{id:'old-session'}],true)).toBe('new-session'));
});
