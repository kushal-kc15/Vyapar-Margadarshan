import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Loader2 } from 'lucide-react';
import AuthLayout from '../components/AuthLayout.jsx';
import Button from '../components/Button.jsx';
import { Input } from '../components/Field.jsx';
import api from '../lib/api.js';
import { useToast } from '../components/Toast.jsx';

export default function ForgotPassword() {
  const toast = useToast();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState('');

  const normalizedEmail = useMemo(() => email.trim().toLowerCase(), [email]);

  const submit = async (e) => {
    e.preventDefault();
    setErr('');

    if (!normalizedEmail) {
      setErr('Enter the email you signed up with.');
      return;
    }

    setLoading(true);
    try {
      await api.post('/auth/request-password-reset/', { email: normalizedEmail });
      setDone(true);
      toast.success('Reset link sent if that email exists.');
    } catch {
      // Neutral messaging – never confirm existence.
      toast.error('Could not send the reset link. Try again in a moment.');
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
        <div className="w-full text-center">
          <h1 className="font-display text-3xl sm:text-4xl font-medium text-ink leading-tight tracking-tight">
            {done ? 'Check your inbox' : 'Reset your password'}
          </h1>
          <p className="mt-2 text-sm text-ink-muted">
            {done ? (
              <>
                If an account exists for <span className="font-medium text-ink">{normalizedEmail}</span>, we sent a reset link. The link expires in one hour.
              </>
            ) : (
              'Enter your email and we’ll send a reset link if an account exists.'
            )}
          </p>

          {!done ? (
            <form onSubmit={submit} className="mt-8 space-y-5 text-left" noValidate>
              <Input
                type="email"
                label="Email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                error={err}
                required
                placeholder="you@company.com"
                autoComplete="email"
              />
              <Button
                type="submit"
                variant="primary"
                size="lg"
                className="w-full"
                disabled={loading}
                iconRight={!loading ? <ArrowRight size={16} /> : <Loader2 size={16} className="animate-spin" />}
              >
                {loading ? 'Sending reset link…' : 'Send reset link'}
              </Button>
              <p className="text-xs text-ink-muted text-center">
                We’ll only send the link if the email matches an account.
              </p>
            </form>
          ) : (
            <div className="mt-8 space-y-4 text-center">
              <Button as={Link} to="/login" variant="ghost" size="lg" className="w-full">
                Back to sign in
              </Button>
              <p className="text-xs text-ink-muted">
                If you don’t see the email, check your spam folder and try again.
              </p>
            </div>
          )}
        </div>
    </AuthLayout>
  );
}
