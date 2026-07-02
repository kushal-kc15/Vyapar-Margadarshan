import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AlertTriangle, ArrowRight, Check, Eye, EyeOff, Loader2 } from 'lucide-react';
import AuthLayout from '../components/AuthLayout.jsx';
import Button from '../components/Button.jsx';
import { Input } from '../components/Field.jsx';
import api from '../lib/api.js';
import { useToast } from '../components/Toast.jsx';

export default function ResetPassword() {
  const { token } = useParams();
  const [params] = useSearchParams();
  const resetToken = token ?? params.get('token') ?? '';
  const navigate = useNavigate();
  const toast = useToast();

  const [pw, setPw] = useState('');
  const [pw2, setPw2] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [showPw2, setShowPw2] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState({});
  const [tokenState, setTokenState] = useState(resetToken.trim() ? 'ready' : 'invalid');

  useEffect(() => {
    setTokenState(resetToken.trim() ? 'ready' : 'invalid');
  }, [resetToken]);

  const pwChecks = useMemo(
    () => [
      { ok: pw.length >= 8, label: '8 characters or more' },
      { ok: /[A-Z]/.test(pw) && /[a-z]/.test(pw), label: 'Upper and lower case' },
      { ok: /\d/.test(pw), label: 'A number' },
    ],
    [pw]
  );

  const pwOk = pwChecks.every((c) => c.ok);
  const tokenMissing = resetToken.trim().length === 0;
  const tokenInvalid = tokenState === 'invalid' || tokenMissing;

  const submit = async (e) => {
    e.preventDefault();
    setErr({});

    if (tokenMissing) {
      setTokenState('invalid');
      return;
    }

    const next = {};
    if (pw.length < 8) next.password = 'Use at least 8 characters';
    if (pw !== pw2) next.password2 = 'Passwords do not match';
    if (Object.keys(next).length) {
      setErr(next);
      return;
    }

    setLoading(true);
    try {
      await api.post('/auth/reset-password/', { token: resetToken, new_password: pw });
      toast.success('Password updated. You can sign in now.');
      navigate('/login', { replace: true });
    } catch (e2) {
      const data = e2?.response?.data;
      const fieldErrs = {};

      if (data && typeof data === 'object') {
        Object.entries(data).forEach(([k, v]) => {
          fieldErrs[k] = Array.isArray(v) ? v[0] : String(v);
        });
      }

      if (Object.keys(fieldErrs).length) {
        setErr(fieldErrs);
        setTokenState(fieldErrs.token || fieldErrs.detail ? 'invalid' : 'ready');
        toast.error(fieldErrs.detail || 'Please check the form.');
      } else {
        setErr({ password: 'This reset link is no longer valid.' });
        setTokenState('invalid');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthLayout
      headerAction={
        <Link to="/login" className="text-sm text-ink-soft hover:text-ink transition-colors">
          Back to sign in
        </Link>
      }
    >
        <div className="w-full">
          {tokenInvalid && (
            <div className="text-center space-y-4">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-cinnabar-50 border border-cinnabar-200 text-cinnabar-600">
                <AlertTriangle size={24} strokeWidth={1.5} />
              </div>
              <div>
                <h1 className="font-display text-3xl sm:text-4xl font-medium text-ink leading-tight tracking-tight">
                  {tokenMissing ? 'Reset link is missing' : 'Reset link not valid'}
                </h1>
                <p className="mt-2 text-sm text-ink-muted">
                  {tokenMissing
                    ? 'Open the password reset email again or request a new reset link.'
                    : 'This link may have expired or already been used. Request a new link or sign in.'}
                </p>
              </div>

              <div className="pt-2 space-y-3">
                <Button as={Link} to="/login" variant="primary" size="lg" className="w-full">
                  Back to sign in
                </Button>
                <Link to="/forgot-password" className="text-sm text-ink-muted hover:text-ink transition-colors">
                  Request a new reset link
                </Link>
              </div>
            </div>
          )}

          {!tokenInvalid && (
            <>
              <div className="text-center">
                <h1 className="font-display text-3xl sm:text-4xl font-medium text-ink leading-tight tracking-tight">
                  Choose a new password
                </h1>
                <p className="mt-2 text-sm text-ink-muted">
                  Use at least 8 characters. This will replace the password for your account.
                </p>
              </div>

              <form onSubmit={submit} className="mt-8 space-y-5" noValidate>
                <Input
                  type={showPw ? 'text' : 'password'}
                  label="New password"
                  value={pw}
                  onChange={(e) => setPw(e.target.value)}
                  error={err.password}
                  autoComplete="new-password"
                  required
                  placeholder="At least 8 characters"
                  rightElement={
                    <button
                      type="button"
                      onClick={() => setShowPw((s) => !s)}
                      className="inline-flex items-center justify-center text-ink-muted hover:text-ink w-7 h-7 rounded-full transition-colors"
                      aria-label={showPw ? 'Hide password' : 'Show password'}
                    >
                      {showPw ? <EyeOff size={16} strokeWidth={1.8} /> : <Eye size={16} strokeWidth={1.8} />}
                    </button>
                  }
                />

                {(pw.length > 0 || err.password) && (
                  <ul className="grid grid-cols-1 gap-1 text-xs text-ink-muted -mt-2">
                    {pwChecks.map((c) => (
                      <li key={c.label} className="flex items-center gap-1.5">
                        <Check
                          size={12}
                          className={c.ok ? 'text-moss-600' : 'text-ink-faint'}
                          strokeWidth={2}
                        />
                        <span className={c.ok ? 'text-ink-soft' : ''}>{c.label}</span>
                      </li>
                    ))}
                  </ul>
                )}

                <Input
                  type={showPw2 ? 'text' : 'password'}
                  label="Confirm new password"
                  value={pw2}
                  onChange={(e) => setPw2(e.target.value)}
                  error={err.password2}
                  autoComplete="new-password"
                  required
                  placeholder="Re-type your new password"
                  rightElement={
                    <button
                      type="button"
                      onClick={() => setShowPw2((s) => !s)}
                      className="inline-flex items-center justify-center text-ink-muted hover:text-ink w-7 h-7 rounded-full transition-colors"
                      aria-label={showPw2 ? 'Hide password' : 'Show password'}
                    >
                      {showPw2 ? <EyeOff size={16} strokeWidth={1.8} /> : <Eye size={16} strokeWidth={1.8} />}
                    </button>
                  }
                />

                <Button
                  type="submit"
                  variant="primary"
                  size="lg"
                  className="w-full"
                  disabled={loading || !pwOk}
                  iconRight={
                    loading ? <Loader2 size={16} className="animate-spin" /> : <ArrowRight size={16} />
                  }
                >
                  {loading ? 'Saving password…' : 'Set new password'}
                </Button>

                <div className="flex items-center justify-center pt-1">
                  <Link to="/login" className="text-sm text-ink-muted hover:text-ink transition-colors">
                    Back to sign in
                  </Link>
                </div>
              </form>
            </>
          )}
        </div>
    </AuthLayout>
  );
}
