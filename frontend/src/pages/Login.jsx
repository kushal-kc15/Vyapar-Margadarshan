import { useEffect, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowRight, Eye, EyeOff, Mail, RotateCcw, ShieldCheck } from 'lucide-react';
import AuthLayout from '../components/AuthLayout.jsx';
import Button from '../components/Button.jsx';
import { Checkbox, Input } from '../components/Field.jsx';
import GoogleSignInButton from '../components/GoogleSignInButton.jsx';
import { useAuth } from '../context/AuthContext.jsx';
import { useToast } from '../components/Toast.jsx';
import {
  extractInviteTokenFromPath,
  getInvitePath,
  getInviteRegisterPath,
  getSafeNextPath,
  readPendingInviteToken,
  storePendingInviteToken,
} from '../lib/inviteFlow.js';

export default function Login() {
  const {
    login,
    googleLogin,
    verifyTwoFactorCode,
    sendTwoFactorCode,
    resendVerification,
  } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const loc = useLocation();
  const [params] = useSearchParams();

  const [view, setView] = useState('password'); // 'password' | '2fa' | 'unverified'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [rememberMe, setRememberMe] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [attemptsLeft, setAttemptsLeft] = useState(null);
  const [resendCooldown, setResendCooldown] = useState(0);
  const codeRefs = useRef([]);

  const inviteParam = params.get('invite') || '';
  const nextPath = getSafeNextPath(params.get('next') || '');
  const nextInviteToken = extractInviteTokenFromPath(nextPath);
  const pendingInvite = inviteParam || nextInviteToken || readPendingInviteToken();

  useEffect(() => {
    if (pendingInvite) storePendingInviteToken(pendingInvite);
  }, [pendingInvite]);

  useEffect(() => {
    if (resendCooldown <= 0) return undefined;
    const t = setTimeout(() => setResendCooldown((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [resendCooldown]);

  const destination = (authData) => {
    if (nextPath) return nextPath;
    if (pendingInvite) return getInvitePath(pendingInvite);
    const organization = Object.prototype.hasOwnProperty.call(
      authData ?? {},
      'active_organization',
    )
      ? authData.active_organization
      : authData?.organization ?? null;
    const memberships = Array.isArray(authData?.memberships) ? authData.memberships : [];
    if (!organization && memberships.length > 1) return '/workspace/start';
    if (!organization && memberships.length === 1) return loc.state?.from || '/dashboard';
    if (!organization) return '/workspace/start';
    return loc.state?.from || '/dashboard';
  };

  const submitPassword = async (e) => {
    e?.preventDefault();
    setErrors({});
    setAttemptsLeft(null);
    if (!email) return setErrors({ email: 'Required' });
    if (!password) return setErrors({ password: 'Required' });
    setLoading(true);
    try {
      const data = await login(email.trim().toLowerCase(), password);
      if (data?.requires_2fa) {
        setView('2fa');
        setResendCooldown(60);
        toast.info(data.message || 'Check your email for a 6-digit code');
        return;
      }
      toast.success('Welcome back');
      navigate(destination(data), { replace: true });
    } catch (err) {
      const data = err?.response?.data || {};
      if (data.email_not_verified) {
        setView('unverified');
        return;
      }
      const msg = data.detail || data.error || data.non_field_errors?.[0] || 'Email or password is incorrect.';
      if (typeof data.attempts_left === 'number') {
        setAttemptsLeft(data.attempts_left);
        setErrors({
          password: `${msg} (${data.attempts_left} attempt${data.attempts_left === 1 ? '' : 's'} left)`,
        });
      } else {
        setErrors({ password: msg });
      }
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const submitOtp = async (e) => {
    e?.preventDefault();
    const otpCode = code.join('');
    if (otpCode.length !== 6) {
      return setErrors({ code: 'Enter the 6-digit code from your email' });
    }
    setErrors({});
    setLoading(true);
    try {
      const data = await verifyTwoFactorCode({
        email: email.trim().toLowerCase(),
        otpCode,
        rememberMe,
      });
      toast.success('Welcome back');
      navigate(destination(data), { replace: true });
    } catch (err) {
      const msg = err?.response?.data?.error || 'Invalid or expired code';
      setErrors({ code: msg });
      toast.error(msg);
      setCode(['', '', '', '', '', '']);
      codeRefs.current[0]?.focus();
    } finally {
      setLoading(false);
    }
  };

  const handleOtpChange = (idx, val) => {
    const digit = val.replace(/\D/g, '').slice(-1);
    const next = [...code];
    next[idx] = digit;
    setCode(next);
    if (digit && idx < 5) codeRefs.current[idx + 1]?.focus();
  };

  const handleOtpKeyDown = (idx, e) => {
    if (e.key === 'Backspace' && !code[idx] && idx > 0) {
      codeRefs.current[idx - 1]?.focus();
    }
  };

  const handleOtpPaste = (e) => {
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    if (!pasted) return;
    e.preventDefault();
    const next = ['', '', '', '', '', ''];
    for (let i = 0; i < pasted.length; i += 1) next[i] = pasted[i];
    setCode(next);
    const last = Math.min(pasted.length, 5);
    codeRefs.current[last]?.focus();
  };

  const resendCode = async () => {
    if (resendCooldown > 0) return;
    try {
      await sendTwoFactorCode({ email: email.trim().toLowerCase(), password });
      toast.success('A new code is on the way');
      setResendCooldown(60);
    } catch (err) {
      const msg = err?.response?.data?.error || 'Could not resend the code';
      toast.error(msg);
    }
  };

  const handleGoogle = async (accessToken) => {
    setGoogleLoading(true);
    setErrors({});
    try {
      const data = await googleLogin(accessToken);
      if (data?.requires_2fa) {
        setEmail(data.email || '');
        setView('2fa');
        setResendCooldown(60);
        toast.info(data.message || 'Two-factor code sent to your Google account email');
        return;
      }
      toast.success('Welcome back');
      navigate(destination(data), { replace: true });
    } catch (err) {
      const msg = err?.response?.data?.error || 'Google sign-in failed';
      toast.error(msg);
    } finally {
      setGoogleLoading(false);
    }
  };

  const handleResendVerification = async () => {
    setResendLoading(true);
    try {
      await resendVerification(email.trim().toLowerCase());
      toast.success('Verification email sent');
    } catch (err) {
      const msg = err?.response?.data?.error || 'Could not resend the email';
      toast.error(msg);
    } finally {
      setResendLoading(false);
    }
  };

  return (
    <AuthLayout
      className="auth-light"
      cardClassName="-translate-y-4 sm:-translate-y-6"
      headerAction={
        view === 'password' ? (
            <Link
              to={pendingInvite ? getInviteRegisterPath(pendingInvite) : "/register"}
              className="text-sm text-ink-soft hover:text-ink transition-colors"
            >
              Need an account? <span className="text-cinnabar-600 font-medium">Create one</span>
            </Link>
        ) : null
      }
    >
          <div className="w-full">
            {view === 'password' && (
              <>
                <h1 className="font-display text-3xl sm:text-4xl font-medium text-ink leading-tight tracking-tight">
                  Welcome back
                </h1>
                <p className="mt-2 text-sm text-ink-muted">
                  Sign in to manage your workspace expenses.
                </p>

                {pendingInvite && (
                  <div className="mt-5 rounded-sm border border-rule bg-paper-deep px-3 py-2 text-xs text-ink-soft">
                    You have an invitation. We’ll add you to the workspace after sign-in.
                  </div>
                )}

                <div className="mt-8 space-y-5">
                  <GoogleSignInButton
                    onSuccess={handleGoogle}
                    onError={() => toast.error('Google sign-in failed')}
                    disabled={googleLoading || loading}
                  />

                  <div className="flex items-center gap-3">
                    <span className="h-px flex-1 bg-rule" />
                    <span className="text-micro uppercase tracking-eyebrow text-ink-faint">
                      or with email
                    </span>
                    <span className="h-px flex-1 bg-rule" />
                  </div>

                  <form onSubmit={submitPassword} className="space-y-5" noValidate>
                    <Input
                      type="email"
                      label="Email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      error={errors.email}
                      autoComplete="email"
                      required
                      placeholder="you@pasal.com"
                    />
                    <div>
                      <Input
                        type={showPw ? 'text' : 'password'}
                        label="Password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        error={errors.password}
                        autoComplete="current-password"
                        required
                        placeholder="••••••••"
                      />
                      <div className="flex items-center justify-between mt-2 -mb-1">
                        <button
                          type="button"
                          onClick={() => setShowPw((s) => !s)}
                          className="text-xs text-ink-muted hover:text-ink inline-flex items-center gap-1"
                        >
                          {showPw ? <EyeOff size={12} /> : <Eye size={12} />}
                          {showPw ? 'Hide' : 'Show'} password
                        </button>
                        <Link to="/forgot-password" className="text-xs text-ink-muted hover:text-ink transition-colors">
                          Forgot password?
                        </Link>
                      </div>
                      {typeof attemptsLeft === 'number' && attemptsLeft > 0 && (
                        <p className="mt-2 text-xs text-cinnabar-600">
                          {attemptsLeft} attempt{attemptsLeft === 1 ? '' : 's'} left before your account is locked.
                        </p>
                      )}
                    </div>
                    <Checkbox
                      label="Keep me signed in for 30 days"
                      checked={rememberMe}
                      onChange={(e) => setRememberMe(e.target.checked)}
                    />
                    <Button
                      type="submit"
                      variant="primary"
                      size="lg"
                      className="w-full"
                      disabled={loading}
                      iconRight={!loading && <ArrowRight size={16} />}
                    >
                      {loading ? 'Signing in…' : 'Sign in'}
                    </Button>
                  </form>
                </div>
              </>
            )}

            {view === '2fa' && (
              <>
                <h1 className="font-display text-3xl sm:text-4xl font-medium text-ink leading-tight tracking-tight">
                  Verify your code
                </h1>
                <p className="mt-2 text-sm text-ink-muted">
                  Enter the 6-digit code we sent to{' '}
                  <span className="text-ink font-medium">{email}</span>.
                </p>

                <form onSubmit={submitOtp} className="mt-8 space-y-5" noValidate>
                  <div>
                    <label className="field-label">Verification code</label>
                    <div className="mt-2 grid grid-cols-6 gap-2" onPaste={handleOtpPaste}>
                      {code.map((c, i) => (
                        <input
                          key={i}
                          ref={(el) => (codeRefs.current[i] = el)}
                          type="text"
                          inputMode="numeric"
                          maxLength={1}
                          value={c}
                          onChange={(e) => handleOtpChange(i, e.target.value)}
                          onKeyDown={(e) => handleOtpKeyDown(i, e)}
                          className="h-12 w-full min-w-0 text-center text-lg font-medium text-ink num bg-paper border border-rule rounded-xs focus:border-cinnabar-500 focus:outline-none focus:ring-2 focus:ring-cinnabar-500/20 transition-shadow"
                          aria-label={`Digit ${i + 1}`}
                        />
                      ))}
                    </div>
                    {errors.code && <p className="field-error mt-2">{errors.code}</p>}
                  </div>

                  <Checkbox
                    label="Trust this device for 30 days"
                    checked={rememberMe}
                    onChange={(e) => setRememberMe(e.target.checked)}
                  />

                  <Button
                    type="submit"
                    variant="primary"
                    size="lg"
                    className="w-full"
                    disabled={loading}
                    iconRight={!loading && <ShieldCheck size={16} />}
                  >
                    {loading ? 'Verifying…' : 'Verify & sign in'}
                  </Button>

                  <div className="flex flex-col gap-3 text-sm pt-1 sm:flex-row sm:items-center sm:justify-between">
                    <button
                      type="button"
                      onClick={() => {
                        setView('password');
                        setCode(['', '', '', '', '', '']);
                        setErrors({});
                      }}
                      className="text-ink-muted hover:text-ink transition-colors"
                    >
                      ← Back to sign in
                    </button>
                    <button
                      type="button"
                      onClick={resendCode}
                      disabled={resendCooldown > 0}
                      className="text-cinnabar-600 hover:text-cinnabar-700 disabled:text-ink-faint disabled:cursor-not-allowed inline-flex items-center gap-1 transition-colors"
                    >
                      <RotateCcw size={12} />
                      {resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend code'}
                    </button>
                  </div>
                </form>
              </>
            )}

            {view === 'unverified' && (
              <>
                <div className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-cinnabar-50 border border-cinnabar-200 text-cinnabar-600 mb-4">
                  <Mail size={18} />
                </div>
                <h1 className="font-display text-3xl sm:text-4xl font-medium text-ink leading-tight tracking-tight">
                  Verify your email
                </h1>
                <p className="mt-2 text-sm text-ink-muted">
                  We sent a verification link to{' '}
                  <span className="text-ink font-medium">{email}</span>. Open it to activate your account.
                </p>

                <div className="mt-8 space-y-3">
                  <Button
                    type="button"
                    variant="primary"
                    size="lg"
                    className="w-full"
                    onClick={handleResendVerification}
                    disabled={resendLoading}
                  >
                    {resendLoading ? 'Sending…' : 'Resend verification email'}
                  </Button>
                  <button
                    type="button"
                    onClick={() => {
                      setView('password');
                      setErrors({});
                    }}
                    className="w-full text-sm text-ink-muted hover:text-ink transition-colors"
                  >
                    ← Use a different email
                  </button>
                </div>
              </>
            )}
          </div>
    </AuthLayout>
  );
}
