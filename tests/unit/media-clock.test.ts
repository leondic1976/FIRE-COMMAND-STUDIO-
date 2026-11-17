import {describe,it,expect} from 'vitest';
import {mediaClock} from '../../packages/domain-schemas/media-clock';
const cue={binding_id:'binding-synthetic',feature_id:'B01-F02-Z01',clip_start_seconds:3,clip_end_seconds:12};
describe('영상과 훈련시계 동기',()=>{
 it('늦은 접속은 공개 훈련시각과 클립 오프셋으로 현재 위치를 복원한다',()=>expect(mediaClock(cue,20,24,'RUNNING')).toEqual({target:7,playing:true}));
 it('일시정지·과거 재생은 동일 위치에 정지하고 재개는 그 위치에서 이어간다',()=>{expect(mediaClock(cue,20,24,'PAUSED')).toEqual({target:7,playing:false});expect(mediaClock(cue,20,24,'REPLAY')).toEqual({target:7,playing:false});const resumed=mediaClock(cue,20,24.1,'RUNNING');expect(resumed.target).toBeCloseTo(7.1,6);expect(resumed.playing).toBe(true);});
 it('공개 이전과 클립 종료를 넘지 않는다',()=>{expect(mediaClock(cue,20,18,'REPLAY')).toEqual({target:3,playing:false});expect(mediaClock(cue,20,100,'RUNNING')).toEqual({target:12,playing:false});});
});
