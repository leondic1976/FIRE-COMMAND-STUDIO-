import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({base:'/',plugins:[react()],resolve:{dedupe:['react','react-dom','three']},build:{outDir:'dist',emptyOutDir:true,rollupOptions:{input:{main:'index.html',map:'map-frame.html'}}},server:{strictPort:true,proxy:{'/api':'http://127.0.0.1:8090','/ws':{target:'ws://127.0.0.1:8090',ws:true}}}});
