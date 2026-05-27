/* iter108 — ACTION 2: Reusable real-time API-key validation input.
 *
 * Usage:
 *   <ApiKeyInput
 *     provider="saleshandy"
 *     value={key}
 *     onChange={setKey}
 *     onValidityChange={setIsValid}   // optional — parent uses to toggle Save
 *     placeholder="Paste your Saleshandy key…"
 *   />
 *
 * Behaviour:
 *   - Validates on blur and on every change AFTER a 600ms debounce
 *   - Shows ⏳ while the test call is in-flight
 *   - Shows ✅ + green message on success
 *   - Shows ❌ + red message with provider-specific copy on failure
 *   - Calls `onValidityChange(true|false)` so parents can gate the Save button
 */
import React, { useEffect, useRef, useState } from 'react';
import api from '../config/api';

const ApiKeyInput = ({
  provider,
  value = '',
  onChange,
  onValidityChange,
  placeholder = 'Paste API key…',
  disabled = false,
  testIdBase,
}) => {
  const [status, setStatus] = useState('idle'); // 'idle' | 'checking' | 'valid' | 'invalid'
  const [message, setMessage] = useState('');
  const debounceRef = useRef(null);
  const lastValidated = useRef('');

  const runValidation = async (key) => {
    const trimmed = (key || '').trim();
    if (!trimmed || trimmed.length < 8) {
      setStatus('idle');
      setMessage('');
      onValidityChange?.(false);
      return;
    }
    if (lastValidated.current === trimmed) return;
    lastValidated.current = trimmed;
    setStatus('checking');
    setMessage('Checking with provider…');
    try {
      const { data } = await api.post('/api/integrations/validate-key', {
        provider,
        api_key: trimmed,
      });
      if (data.valid) {
        setStatus('valid');
        setMessage(data.message || 'Key valid — ready to connect.');
        onValidityChange?.(true);
      } else {
        setStatus('invalid');
        setMessage(data.message || 'Provider rejected this key.');
        onValidityChange?.(false);
      }
    } catch (e) {
      setStatus('invalid');
      setMessage(e?.response?.data?.detail || 'Validation request failed.');
      onValidityChange?.(false);
    }
  };

  useEffect(() => {
    if (!value) {
      setStatus('idle');
      setMessage('');
      onValidityChange?.(false);
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runValidation(value), 600);
    return () => debounceRef.current && clearTimeout(debounceRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, provider]);

  const onBlur = () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (value && lastValidated.current !== value.trim()) runValidation(value);
  };

  const borderClass =
    status === 'valid' ? 'border-emerald-400 focus:ring-emerald-300'
    : status === 'invalid' ? 'border-rose-400 focus:ring-rose-300'
    : 'border-slate-300 focus:ring-violet-300';

  const iconBlock = () => {
    if (status === 'checking') return <span className="text-violet-500 animate-pulse" aria-label="checking">⏳</span>;
    if (status === 'valid')    return <span className="text-emerald-600 font-bold" aria-label="valid">✓</span>;
    if (status === 'invalid')  return <span className="text-rose-600 font-bold" aria-label="invalid">✕</span>;
    return null;
  };

  return (
    <div className="w-full">
      <div className={`flex items-center gap-2 rounded-lg border ${borderClass} bg-white px-3 focus-within:ring-2`}>
        <input
          type="password"
          value={value}
          onChange={(e) => onChange?.(e.target.value)}
          onBlur={onBlur}
          placeholder={placeholder}
          disabled={disabled}
          autoComplete="off"
          spellCheck={false}
          className="flex-1 bg-transparent py-2.5 text-sm text-slate-900 outline-none placeholder:text-slate-400 disabled:opacity-50"
          data-testid={testIdBase ? `${testIdBase}-input` : `apikey-input-${provider}`}
        />
        <div className="text-base shrink-0" data-testid={testIdBase ? `${testIdBase}-status-icon` : `apikey-status-${provider}`}>
          {iconBlock()}
        </div>
      </div>
      {message && (
        <div
          className={`mt-1.5 text-xs ${
            status === 'valid' ? 'text-emerald-700'
            : status === 'invalid' ? 'text-rose-700'
            : 'text-slate-500'
          }`}
          data-testid={testIdBase ? `${testIdBase}-message` : `apikey-message-${provider}`}
        >
          {message}
        </div>
      )}
    </div>
  );
};

export default ApiKeyInput;
