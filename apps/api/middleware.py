from starlette.responses import JSONResponse


class BoundedBodyMiddleware:
    """Bound streamed bodies too: Content-Length alone does not cover chunked uploads."""
    def __init__(self,app,max_bytes=15*1024*1024+100000):
        self.app=app;self.max_bytes=max_bytes

    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method'] in ('GET','HEAD','OPTIONS'):
            await self.app(scope,receive,send);return
        chunks=[];total=0
        while True:
            message=await receive()
            if message['type']=='http.disconnect':return
            data=message.get('body',b'');total+=len(data)
            if total>self.max_bytes:
                await JSONResponse({'detail':'요청 크기 제한 초과'},status_code=413)(scope,receive,send);return
            chunks.append(data)
            if not message.get('more_body'):break
        delivered=False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered=True
                return {'type':'http.request','body':b''.join(chunks),'more_body':False}
            return await receive()
        await self.app(scope,replay,send)
