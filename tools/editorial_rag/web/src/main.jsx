import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles.css';

window.addEventListener('unhandledrejection', (event) => {
  if (event.reason?.message?.includes('M_ID') || event.reason?.stack?.includes('200.js')) {
    event.preventDefault();
  }
});

try {
  if (typeof document !== 'undefined' && !document.querySelector('head > script[data-config]')) {
    const script = document.createElement('script');
    script.setAttribute('data-config', JSON.stringify({ config: { properties: { M_ID: '', M_TYPE: '' } } }));
    script.setAttribute('bis_use', '');
    document.head?.appendChild(script);
  }
} catch {}

createRoot(document.getElementById('root')).render(<App />);
