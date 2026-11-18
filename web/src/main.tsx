import { createRoot } from 'react-dom/client';
import App from '../../apps/web/src/App';

// Shared screens use the same authorized API/WS service in the web edition.
createRoot(document.getElementById('root')!).render(<App runtimeTrack="web" />);
