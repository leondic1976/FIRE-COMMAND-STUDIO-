export interface ClockSample {serverMs:number;localMidpointMs:number;roundTripMs:number}
export function serverEpoch(sample:ClockSample,localNow:number){return sample.serverMs+localNow-sample.localMidpointMs;}
export function trainingSeconds(state:{elapsed_seconds:number;status:string;clock_sampled_at?:string;received_at_ms?:number},sample:ClockSample|null,localNow:number){
 if(state.status!=='RUNNING')return state.elapsed_seconds;
 const sampledAt=Date.parse(state.clock_sampled_at||'');
 if(sample&&Number.isFinite(sampledAt))return state.elapsed_seconds+Math.max(0,(serverEpoch(sample,localNow)-sampledAt)/1000);
 return state.elapsed_seconds+Math.max(0,(localNow-(state.received_at_ms??localNow))/1000);
}
