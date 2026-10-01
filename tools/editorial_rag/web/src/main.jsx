import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles.css';

window.addEventListener('unhandledrejection', (event) => {
  if (event.reason?.message?.includes('M_ID')) {
    event.preventDefault();
  }
});

createRoot(document.getElementById('root')).render(<App />);
