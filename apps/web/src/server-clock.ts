import type {SessionState} from '../../../packages/domain-schemas';
import {ClockSample,trainingSeconds} from '../../../packages/domain-schemas/clock-sync';
let sample:ClockSample|null=null,generation=0,lastSync=0,pending:Promise<void>|null=null;
export function resetServerClock(){generation++;sample=null;lastSync=0;pending=null;}
export function sessionElapsed(session:SessionState|null){return session?trainingSeconds(session,sample,performance.now()):0;}
export function calibrateServerClock(){
 if(pending)return pending;
 if(sample&&performance.now()-lastSync<30000)return Promise.resolve();
 const identity=generation;
 pending=(async()=>{let best:ClockSample|null=null;for(let i=0;i<3;i++){
  const start=performance.now();
  try{const response=await fetch('/api/v1/clock',{credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(2500)});if(!response.ok)return;const data=await response.json() as {server_time:string};const end=performance.now(),serverMs=Date.parse(data.server_time),roundTripMs=end-start;
   if(Number.isFinite(serverMs)&&roundTripMs<2000&&(!best||roundTripMs<best.roundTripMs)){best={serverMs,localMidpointMs:(start+end)/2,roundTripMs};if(identity===generation)sample=best;}
  }catch{return;}
 }if(identity===generation)lastSync=performance.now();})().finally(()=>{if(identity===generation)pending=null;});
 return pending;
}
