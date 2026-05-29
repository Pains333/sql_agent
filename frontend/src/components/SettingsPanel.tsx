
import { useEffect, useRef } from 'react';
import { t } from '../i18n';
import { Settings, X, Moon, Sun } from 'lucide-react';
import './SettingsPanel.css';

interface SettingsPanelProps {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  onClose: () => void;
}

export default function SettingsPanel({ theme, onToggleTheme, onClose }: SettingsPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Close when clicking outside
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    // Delay to avoid the opening click
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClick);
    }, 100);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClick);
    };
  }, [onClose]);

  // Close on Escape
  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [onClose]);

  return (
    <>
      <div className="settings-overlay" onClick={onClose} />
      <div className="settings-panel" ref={panelRef}>
        <div className="settings-header">
          <span className="settings-title">
            <Settings size={16} />
            {t('settings.title')}
          </span>
          <button className="settings-close" onClick={onClose}>
            <X size={14} />
          </button>
        </div>

        <div className="settings-body">
          {/* Dark Mode Toggle */}
          <div className="settings-item">
            <span className="settings-item-label">
              {theme === 'dark' ? (
                <Moon size={16} />
              ) : (
                <Sun size={16} />
              )}
              {t('settings.darkMode')}
            </span>
            <label className="toggle-switch">
              <input
                type="checkbox"
                checked={theme === 'dark'}
                onChange={onToggleTheme}
              />
              <span className="toggle-slider" />
            </label>
          </div>

          <div className="settings-version">
            SQL Agent v2.0.0
          </div>
        </div>
      </div>
    </>
  );
}
