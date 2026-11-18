export async function api<T>(path:string, options:RequestInit = {}):Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) headers.set('Content-Type','application/json');
  if (options.method && !['GET','HEAD'].includes(options.method) && !headers.has('Idempotency-Key')) headers.set('Idempotency-Key', crypto.randomUUID());
  const response = await fetch('/api/v1'+path, {...options, headers, credentials:'same-origin'});
  if (!response.ok) {
    if(response.status===401&&typeof window!=='undefined')window.dispatchEvent(new Event('studio:auth-lost'));
    let detail: unknown = response.statusText;
    try {detail = (await response.json()).detail;} catch { /* HTTP text fallback */ }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  return response.json() as Promise<T>;
}
export const post = <T>(path:string, body:unknown={}) => api<T>(path,{method:'POST',body:JSON.stringify(body)});
export async function download(path:string, name:string) {const r=await fetch('/api/v1'+path,{credentials:'same-origin'});if(!r.ok)throw new Error('내보내기 권한과 상태를 확인하세요.');const href=URL.createObjectURL(await r.blob());const a=document.createElement('a');a.href=href;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(href),1000);}
