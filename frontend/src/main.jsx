import { createRoot } from 'react-dom/client';
import Root from './workspace/Root';
import './styles.css';
import './refinements.css';
// A Three.js renderer owns a scarce WebGL context. Avoid React development
// StrictMode's intentional mount/unmount/remount cycle, which discards it.
createRoot(document.getElementById('root')).render(<Root />);
