export async function api<T>(path:string,init:RequestInit={}):Promise<T>{
 const headers=new Headers(init.headers);
 if(init.body&&typeof init.body==='string')headers.set('Content-Type','application/json');
 if(['POST','PUT','DELETE'].includes(init.method||'')&&!headers.has('Idempotency-Key'))headers.set('Idempotency-Key',crypto.randomUUID());
 const response=await fetch(path,{...init,headers,credentials:'same-origin'});
 if(!response.ok){let message=`요청을 처리하지 못했습니다 (${response.status}).`;try{const error=await response.json();message=typeof error.detail==='string'?error.detail:'입력 형식과 최소60초 사건 간격을 확인하세요.';}catch{}throw Error(message);}
 return response.json() as Promise<T>;
}
export const post=<T>(path:string,value:unknown)=>api<T>(path,{method:'POST',body:JSON.stringify(value)});
export async function saveDownload(path:string,name:string){const response=await fetch(path,{credentials:'same-origin'});if(!response.ok)throw Error('파일을 내려받지 못했습니다. 권한과 저장 상태를 확인하세요.');const url=URL.createObjectURL(await response.blob());const anchor=document.createElement('a');anchor.href=url;anchor.download=name;anchor.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
