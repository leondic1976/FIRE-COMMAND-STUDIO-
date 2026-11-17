import type {MediaCue} from './index';

export function mediaClock(cue:MediaCue,releasedAt:number,elapsed:number,status:string){
 const elapsedSinceRelease=Math.max(0,elapsed-releasedAt);
 const target=Math.min(cue.clip_end_seconds,Math.max(cue.clip_start_seconds,cue.clip_start_seconds+elapsedSinceRelease));
 return {target,playing:status==='RUNNING'&&target<cue.clip_end_seconds-.03};
}
