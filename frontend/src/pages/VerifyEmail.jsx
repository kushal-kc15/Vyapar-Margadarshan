import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';
import AuthLayout from '../components/AuthLayout.jsx';
import Button from '../components/Button.jsx';
import api from '../lib/api.js';
import { useToast } from '../components/Toast.jsx';

export default function VerifyEmail() {
  const { token } = useParams();
  const [params] = useSearchParams();
  const verificationToken = token ?? params.get('token') ?? '';
  const [state, setState] = useState(verificationToken.trim() ? 'verifying' : 'error');
  const [msg, setMsg] = useState(verificationToken.trim() ? '' : 'Open the verification email again or request a new account email.');
  const toast = useToast();
  const navigate = useNavigate();

  const verifyEmail = async () => {
    if (!verificationToken.trim()) {
      setState('error');
      setMsg('Open the verification email again or request a new account email.');
      return;
    }

    setState('verifying');
    setMsg('');

    try {
      await api.post('/auth/verify-email/', { token: verificationToken });
      setState('success');
      toast.success('Email verified.');
      setTimeout(() => navigate('/login', { replace: true }), 1800);
    } catch (err) {
      setState('error');
      setMsg(err?.response?.data?.detail || 'This link is invalid or has expired.');
      toast.error('Could not verify this email.');
    }
  };

  useEffect(() => {
    let cancelled = false;

    if (!verificationToken.trim()) {
      setState('error');
      setMsg('Open the verification email again or request a new account email.');
      return () => {
        cancelled = true;
      };
    }

    setState('verifying');
    api.post('/auth/verify-email/', { token: verificationToken })
      .then(() => {
        if (cancelled) return;
        setState('success');
        toast.success('Email verified.');
        setTimeout(() => navigate('/login', { replace: true }), 1800);
      })
      .catch((err) => {
        if (cancelled) return;
        setState('error');
        setMsg(err?.response?.data?.detail || 'This link is invalid or has expired.');
        toast.error('Could not verify this email.');
      });

    return () => {
      cancelled = true;
    };
  }, [verificationToken, toast, navigate]);

  return (
    <AuthLayout
      headerAction={
        <Link to="/login" className="text-sm text-ink-soft hover:text-ink transition-colors">
          Back to sign in
        </Link>
      }
    >
        <div className="w-full text-center">
          {state === 'verifying' && (
            <div className="space-y-4">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-paper-deep text-ink-muted">
                <Loader2 size={24} strokeWidth={1.8} className="animate-spin" />
              </div>
              <div>
                <h1 className="font-display text-3xl sm:text-4xl font-medium text-ink leading-tight tracking-tight">
                  Verifying your email
                </h1>
                <p className="mt-2 text-sm text-ink-muted">
                  Please wait while we confirm your verification link.
                </p>
              </div>
            </div>
          )}

          {state === 'success' && (
            <div className="space-y-4">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-moss-50 border border-moss-200 text-moss-700">
                <CheckCircle2 size={24} strokeWidth={1.8} />
              </div>
              <div>
                <h1 className="font-display text-3xl sm:text-4xl font-medium text-ink leading-tight tracking-tight">
                  Email verified
                </h1>
                <p className="mt-2 text-sm text-ink-muted">
                  Your email is confirmed. Taking you to sign in…
                </p>
              </div>

              <div className="pt-2">
                <Button as={Link} to="/login" variant="secondary" size="lg" className="w-full">
                  Continue to sign in
                </Button>
              </div>
            </div>
          )}

          {state === 'error' && (
            <div className="space-y-4">
              <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-cinnabar-50 border border-cinnabar-200 text-cinnabar-600">
                <AlertTriangle size={24} strokeWidth={1.8} />
              </div>
              <div>
                <h1 className="font-display text-3xl sm:text-4xl font-medium text-ink leading-tight tracking-tight">
                  {verificationToken.trim() ? 'Email not verified' : 'Verification link is missing'}
                </h1>
                <p className="mt-2 text-sm text-ink-muted">
                  {msg}
                </p>
              </div>

              <div className="pt-2 space-y-3">
                <Button
                  type="button"
                  variant="primary"
                  size="lg"
                  className="w-full"
                  onClick={verifyEmail}
                  disabled={state === 'verifying'}
                >
                  Try again
                </Button>
                <Button as={Link} to="/login" variant="secondary" size="lg" className="w-full">
                  Back to sign in
                </Button>
              </div>
            </div>
          )}
        </div>
    </AuthLayout>
  );
}
