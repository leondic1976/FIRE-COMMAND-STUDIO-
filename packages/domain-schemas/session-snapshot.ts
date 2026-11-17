/** An older REST response must never replace a newer authoritative WS version. */
export function latestSnapshot<T extends {id:string;state_version:number;clock_sampled_at?:string}>(current:T|null,incoming:T):T{
 if(!current||current.id!==incoming.id)return incoming;
 if(incoming.state_version<current.state_version)return current;
 if(incoming.state_version===current.state_version){const previous=Date.parse(current.clock_sampled_at||''),next=Date.parse(incoming.clock_sampled_at||'');if(Number.isFinite(previous)&&(!Number.isFinite(next)||next<previous))return current;}
 return incoming;
}
