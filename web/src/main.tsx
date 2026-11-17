import { createRoot } from 'react-dom/client';
import App from '../../apps/web/src/App';

// Shared screens are kept intact while the web-specific runtime is selected.
createRoot(document.getElementById('root')!).render(<App />);
