/* ============================================
   SetupWizard — 3-step configuration dialog
   ============================================ */

import { useState, useEffect } from 'react';
import type { SetupConfig, OllamaModel } from '../types';
import { getOllamaModels, submitSetup } from '../api';
import { t, setLang } from '../i18n';
import type { Lang } from '../i18n';
import './SetupWizard.css';

interface SetupWizardProps {
  onComplete: () => void;
}

const DB_DEFAULT_PORTS: Record<string, number> = {
  postgresql: 5432,
  mysql: 3306,
  oracle: 1521,
};

export default function SetupWizard({ onComplete }: SetupWizardProps) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Config state
  const [language, setLanguage] = useState<Lang>('zh');
  const [modelType, setModelType] = useState<'local' | 'api'>('local');
  const [modelName, setModelName] = useState('');
  const [apiBaseUrl, setApiBaseUrl] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [apiModel, setApiModel] = useState('');
  const [dbType, setDbType] = useState<'postgresql' | 'mysql' | 'oracle'>('postgresql');
  const [dbHost, setDbHost] = useState('localhost');
  const [dbPort, setDbPort] = useState(5432);
  const [dbUser, setDbUser] = useState('');
  const [dbPassword, setDbPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);

  // Ollama models
  const [ollamaModels, setOllamaModels] = useState<OllamaModel[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);

  // Load Ollama models when switching to local
  useEffect(() => {
    if (modelType === 'local') {
      setModelsLoading(true);
      getOllamaModels()
        .then((res) => {
          setOllamaModels(res.models || []);
          if (res.models?.length > 0 && !modelName) {
            setModelName(res.models[0].name);
          }
        })
        .catch(() => setOllamaModels([]))
        .finally(() => setModelsLoading(false));
    }
  }, [modelType]);

  // Update port when db type changes
  useEffect(() => {
    setDbPort(DB_DEFAULT_PORTS[dbType] || 5432);
  }, [dbType]);

  // Sync language
  function handleLangChange(lang: Lang) {
    setLanguage(lang);
    setLang(lang);
  }

  // Format file size
  function formatSize(bytes: number): string {
    if (bytes < 1e9) return `${(bytes / 1e6).toFixed(0)} MB`;
    return `${(bytes / 1e9).toFixed(1)} GB`;
  }

  // Submit
  async function handleFinish() {
    setError('');

    // Validate required fields
    if (modelType === 'api') {
      if (!apiBaseUrl.trim()) { setError(t('error.apiUrlRequired')); return; }
      if (!apiKey.trim()) { setError(t('error.apiKeyRequired')); return; }
      if (!apiModel.trim()) { setError(t('error.apiModelRequired')); return; }
    }
    if (!dbUser.trim()) { setError(t('error.dbUserRequired')); return; }
    if (!dbPassword.trim()) { setError(t('error.dbPasswordRequired')); return; }

    setLoading(true);

    const config: SetupConfig = {
      language,
      model_type: modelType,
      model_name: modelName,
      api_base_url: apiBaseUrl,
      api_key: apiKey,
      api_model: apiModel,
      db_type: dbType,
      db_host: dbHost,
      db_port: dbPort,
      db_user: dbUser,
      db_password: dbPassword,
    };

    try {
      await submitSetup(config);
      onComplete();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="wizard-overlay">
      <div className="wizard-card">
        {/* Header */}
        <div className="wizard-header">
          <h1 className="wizard-title">{t('setup.title')}</h1>
          {/* Step indicators */}
          <div className="step-indicators">
            {[1, 2, 3].map((s) => (
              <div
                key={s}
                className={`step-dot ${s === step ? 'active' : ''} ${s < step ? 'done' : ''}`}
              >
                {s < step ? '✓' : s}
              </div>
            ))}
          </div>
          <div className="step-label">
            {t('setup.step')} {step} / 3
          </div>
        </div>

        {/* Content */}
        <div className="wizard-body">
          {/* ---- STEP 1: Language ---- */}
          {step === 1 && (
            <div className="step-content">
              <h2 className="step-title">{t('step1.title')}</h2>
              <p className="step-desc">{t('step1.desc')}</p>

              <div className="form-group">
                <label className="form-label">{t('step1.label')}</label>
                <select
                  className="form-select"
                  value={language}
                  onChange={(e) => handleLangChange(e.target.value as Lang)}
                >
                  <option value="zh">🇨🇳 中文</option>
                  <option value="en">🇺🇸 English</option>
                </select>
              </div>
            </div>
          )}

          {/* ---- STEP 2: Model ---- */}
          {step === 2 && (
            <div className="step-content">
              <h2 className="step-title">{t('step2.title')}</h2>
              <p className="step-desc">{t('step2.desc')}</p>

              <div className="form-group">
                <label className="form-label">{t('step2.type')}</label>
                <select
                  className="form-select"
                  value={modelType}
                  onChange={(e) => setModelType(e.target.value as 'local' | 'api')}
                >
                  <option value="local">{t('step2.local')}</option>
                  <option value="api">{t('step2.api')}</option>
                </select>
              </div>

              {modelType === 'local' && (
                <>
                  <div className="form-hint">{t('step2.localHint')}</div>
                  <div className="form-group">
                    <label className="form-label">{t('step2.model')}</label>
                    {modelsLoading ? (
                      <div className="form-loading">{t('step2.loading')}</div>
                    ) : ollamaModels.length === 0 ? (
                      <div className="form-warning">{t('step2.noModels')}</div>
                    ) : (
                      <select
                        className="form-select"
                        value={modelName}
                        onChange={(e) => setModelName(e.target.value)}
                      >
                        {ollamaModels.map((m) => (
                          <option key={m.name} value={m.name}>
                            {m.name} ({formatSize(m.size)})
                          </option>
                        ))}
                      </select>
                    )}
                  </div>
                </>
              )}

              {modelType === 'api' && (
                <>
                  <div className="form-group">
                    <label className="form-label">{t('step2.apiUrl')}</label>
                    <input
                      className="form-input"
                      type="text"
                      value={apiBaseUrl}
                      onChange={(e) => setApiBaseUrl(e.target.value)}
                      placeholder={t('step2.apiUrlPlaceholder')}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">{t('step2.apiKey')}</label>
                    <div className="input-with-toggle">
                      <input
                        className="form-input"
                        type={showApiKey ? 'text' : 'password'}
                        value={apiKey}
                        onChange={(e) => setApiKey(e.target.value)}
                        placeholder={t('step2.apiKeyPlaceholder')}
                      />
                      <button
                        className="toggle-btn"
                        type="button"
                        onClick={() => setShowApiKey(!showApiKey)}
                      >
                        {showApiKey ? '🙈' : '👁️'}
                      </button>
                    </div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">{t('step2.apiModel')}</label>
                    <input
                      className="form-input"
                      type="text"
                      value={apiModel}
                      onChange={(e) => setApiModel(e.target.value)}
                      placeholder={t('step2.apiModelPlaceholder')}
                    />
                  </div>
                </>
              )}
            </div>
          )}

          {/* ---- STEP 3: Database ---- */}
          {step === 3 && (
            <div className="step-content">
              <h2 className="step-title">{t('step3.title')}</h2>
              <p className="step-desc">{t('step3.desc')}</p>

              <div className="form-group">
                <label className="form-label">{t('step3.type')}</label>
                <select
                  className="form-select"
                  value={dbType}
                  onChange={(e) => setDbType(e.target.value as 'postgresql' | 'mysql' | 'oracle')}
                >
                  <option value="postgresql">PostgreSQL</option>
                  <option value="mysql">🐬 MySQL</option>
                  <option value="oracle">🔶 Oracle</option>
                </select>
              </div>

              <div className="form-row">
                <div className="form-group flex-2">
                  <label className="form-label">{t('step3.host')}</label>
                  <input
                    className="form-input"
                    type="text"
                    value={dbHost}
                    onChange={(e) => setDbHost(e.target.value)}
                    placeholder="localhost"
                  />
                </div>
                <div className="form-group flex-1">
                  <label className="form-label">{t('step3.port')}</label>
                  <input
                    className="form-input"
                    type="number"
                    value={dbPort}
                    onChange={(e) => setDbPort(Number(e.target.value))}
                  />
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">{t('step3.user')}</label>
                <input
                  className="form-input"
                  type="text"
                  value={dbUser}
                  onChange={(e) => setDbUser(e.target.value)}
                  placeholder={t('step3.userPlaceholder')}
                />
              </div>

              <div className="form-group">
                <label className="form-label">{t('step3.password')}</label>
                <div className="input-with-toggle">
                  <input
                    className="form-input"
                    type={showPassword ? 'text' : 'password'}
                    value={dbPassword}
                    onChange={(e) => setDbPassword(e.target.value)}
                    placeholder={t('step3.passwordPlaceholder')}
                  />
                  <button
                    className="toggle-btn"
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? '🙈' : '👁️'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Error */}
          {error && (
            <div className="wizard-error">
              <span className="error-icon">❌</span>
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="wizard-footer">
          <div className="footer-left">
            {step > 1 && (
              <button
                className="wizard-btn btn-secondary"
                onClick={() => { setStep(step - 1); setError(''); }}
                disabled={loading}
              >
                ← {t('setup.prev')}
              </button>
            )}
          </div>
          <div className="footer-right">
            {step < 3 ? (
              <button
                className="wizard-btn btn-primary"
                onClick={() => { setStep(step + 1); setError(''); }}
              >
                {t('setup.next')} →
              </button>
            ) : (
              <button
                className="wizard-btn btn-finish"
                onClick={handleFinish}
                disabled={loading}
              >
                {loading ? (
                  <>
                    <span className="btn-spinner" />
                    {t('setup.connecting')}
                  </>
                ) : (
                  t('setup.finish')
                )}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
