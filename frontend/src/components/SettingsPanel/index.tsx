import { useEffect, useRef } from 'react';
import type { Lang } from '../../i18n';
import { t } from '../../i18n';
import {
  Settings, X, Moon, Sun, Globe,
} from 'lucide-react';
import './index.css';

interface SettingsPanelProps {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  lang: Lang;
  onLangChange: (lang: Lang) => void;
  onClose: () => void;
}

export default function SettingsPanel({
  theme, onToggleTheme,
  lang, onLangChange,
  onClose,
}: SettingsPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (panelRef.current && !panelRef.current.contains(e.target as Node)) {
        onClose();
      }
    }
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClick);
    }, 100);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClick);
    };
  }, [onClose]);

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
          {/* 1. Language */}
          <div className="settings-item">
            <span className="settings-item-label">
              <Globe size={16} />
              {t('settings.language')}
            </span>
            <div className="lang-switch">
              <button
                className={`lang-btn ${lang === 'zh' ? 'active' : ''}`}
                onClick={() => onLangChange('zh')}
              >
                中文
              </button>
              <button
                className={`lang-btn ${lang === 'en' ? 'active' : ''}`}
                onClick={() => onLangChange('en')}
              >
                EN
              </button>
            </div>
          </div>

          {/* 2. Dark Mode */}
          <div className="settings-item">
            <span className="settings-item-label">
              {theme === 'dark' ? <Moon size={16} /> : <Sun size={16} />}
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


        </div>
      </div>
    </>
  );
}
