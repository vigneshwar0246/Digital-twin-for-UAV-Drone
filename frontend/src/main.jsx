import React from 'react';
import { createRoot } from 'react-dom/client';
import Root from './workspace/Root';
import './styles.css';
import './refinements.css';
createRoot(document.getElementById('root')).render(<React.StrictMode><Root /></React.StrictMode>);
