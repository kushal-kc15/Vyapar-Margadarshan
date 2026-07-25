from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from organizations.models import Invitation, Organization, OrganizationMember
from users.auth_utils import hash_token
from users.models import PasswordResetToken, TwoFactorOTP

User = get_user_model()


class RegistrationWorkflowTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()

    def tearDown(self):
        cache.clear()

    def registration_payload(self, **overrides):
        payload = {
            'email': 'newuser@example.com',
            'password': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'first_name': 'New',
            'last_name': 'User',
            'business_name': 'New Business',
            'phone_number': '',
        }
        payload.update(overrides)
        return payload

    def test_register_without_invite_creates_standalone_user(self):
        response = self.client.post('/api/auth/register/', self.registration_payload())

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='newuser@example.com')
        self.assertEqual(user.username, 'newuser')
        self.assertFalse(OrganizationMember.objects.filter(user=user).exists())
        self.assertEqual(response.data['memberships'], [])
        self.assertIsNone(response.data['active_organization'])
        self.assertIsNone(response.data['role'])

    def test_register_without_username_succeeds_and_generates_username_from_email(self):
        response = self.client.post(
            '/api/auth/register/',
            self.registration_payload(email='kishmatkc5@gmail.com'),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='kishmatkc5@gmail.com')
        self.assertEqual(user.username, 'kishmatkc5')

    def test_register_username_collision_generates_numeric_suffix(self):
        User.objects.create_user(
            username='kishmatkc5',
            email='existing@example.com',
            password='StrongPass123!',
        )

        response = self.client.post(
            '/api/auth/register/',
            self.registration_payload(email='kishmatkc5@gmail.com'),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='kishmatkc5@gmail.com')
        self.assertEqual(user.username, 'kishmatkc5_1')

    def test_register_duplicate_email_fails_clearly(self):
        User.objects.create_user(
            username='existing',
            email='newuser@example.com',
            password='StrongPass123!',
        )

        response = self.client.post('/api/auth/register/', self.registration_payload())

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data['email'][0],
            'An account with this email already exists. Please sign in.',
        )

    def test_register_with_invite_links_user_to_organization(self):
        org = Organization.objects.create(name='Inviting Org')
        owner = User.objects.create_user(
            username='owner',
            email='owner@example.com',
            password='StrongPass123!',
        )
        OrganizationMember.objects.create(organization=org, user=owner, role='OWNER')
        invitation = Invitation.objects.create(
            organization=org,
            email='invited@example.com',
            role='STAFF',
            invited_by=owner,
            expires_at=timezone.now() + timedelta(days=7),
        )

        response = self.client.post(
            '/api/auth/register/',
            self.registration_payload(
                email='invited@example.com',
                invite_token=str(invitation.token),
            ),
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='invited@example.com')
        self.assertEqual(user.username, 'invited')
        member = OrganizationMember.objects.get(user=user)
        self.assertEqual(member.organization, org)
        self.assertEqual(member.role, 'STAFF')
        self.assertEqual(response.data['active_organization']['id'], org.id)
        invitation.refresh_from_db()
        self.assertTrue(invitation.is_used)

    def test_register_rolls_back_user_when_verification_email_fails(self):
        with patch('users.auth_utils.send_mail', side_effect=RuntimeError('SMTP down')):
            response = self.client.post('/api/auth/register/', self.registration_payload())

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertFalse(User.objects.filter(email='newuser@example.com').exists())
        self.assertIn('verification email', response.data['error'])


class AuthThrottleTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()
        self.user = User.objects.create_user(
            username='throttleuser',
            email='throttle@example.com',
            password='StrongPass123!',
            email_verified=True,
        )

    def tearDown(self):
        cache.clear()

    def test_login_endpoint_returns_429_after_rate_limit(self):
        payload = {
            'email': self.user.email,
            'password': 'wrong-password',
        }
        responses = [
            self.client.post('/api/auth/login/', payload, format='json')
            for _ in range(6)
        ]

        self.assertEqual(responses[0].status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(responses[-1].status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class AuthTokenStorageTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()
        self.user = User.objects.create_user(
            username='tokenuser',
            email='token@example.com',
            password='StrongPass123!',
            email_verified=False,
        )

    def tearDown(self):
        cache.clear()

    def test_resend_verification_stores_hash_and_verifies_raw_token(self):
        sent_tokens = []

        def capture_email(user, token, *args, **kwargs):
            sent_tokens.append(token)
            return True

        with patch('users.security_views.send_verification_email', side_effect=capture_email):
            response = self.client.post(
                '/api/auth/resend-verification/',
                {'email': self.user.email},
                format='json',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        raw_token = sent_tokens[0]
        self.assertNotEqual(self.user.email_verification_token, raw_token)
        self.assertEqual(self.user.email_verification_token, hash_token(raw_token))
        self.assertIsNotNone(self.user.email_verification_token_created_at)

        verify_response = self.client.post(
            '/api/auth/verify-email/',
            {'token': raw_token},
            format='json',
        )

        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)
        self.assertIsNone(self.user.email_verification_token)
        self.assertIsNone(self.user.email_verification_token_created_at)

    def test_password_reset_stores_hash_and_invalidates_previous_token(self):
        self.user.email_verified = True
        self.user.save(update_fields=['email_verified'])
        sent_tokens = []

        def capture_email(user, token):
            sent_tokens.append(token)
            return True

        with patch('users.security_views.send_password_reset_email', side_effect=capture_email):
            first_response = self.client.post(
                '/api/auth/request-password-reset/',
                {'email': self.user.email},
                format='json',
            )
            second_response = self.client.post(
                '/api/auth/request-password-reset/',
                {'email': self.user.email},
                format='json',
            )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(sent_tokens), 2)

        first_token, second_token = sent_tokens
        stored_tokens = list(PasswordResetToken.objects.filter(user=self.user).order_by('id'))
        self.assertEqual(stored_tokens[0].token, hash_token(first_token))
        self.assertEqual(stored_tokens[1].token, hash_token(second_token))
        self.assertNotEqual(stored_tokens[0].token, first_token)
        self.assertTrue(stored_tokens[0].used)
        self.assertFalse(stored_tokens[1].used)

        old_reset_response = self.client.post(
            '/api/auth/reset-password/',
            {'token': first_token, 'new_password': 'NewStrongPass123!'},
            format='json',
        )
        self.assertEqual(old_reset_response.status_code, status.HTTP_400_BAD_REQUEST)

        new_reset_response = self.client.post(
            '/api/auth/reset-password/',
            {'token': second_token, 'new_password': 'NewStrongPass123!'},
            format='json',
        )
        self.assertEqual(new_reset_response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewStrongPass123!'))


class TwoFactorAuthenticationTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()
        self.user = User.objects.create_user(
            username='twofactor',
            email='twofactor@example.com',
            password='StrongPass123!',
            email_verified=True,
            two_factor_enabled=True,
        )

    def tearDown(self):
        cache.clear()

    def test_login_bypasses_otp_while_login_2fa_is_disabled(self):
        with patch('users.security_views.send_2fa_otp_email') as send_otp:
            login_response = self.client.post(
                '/api/auth/login/',
                {
                    'email': self.user.email,
                    'password': 'StrongPass123!',
                },
                format='json',
            )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertNotIn('requires_2fa', login_response.data)
        self.assertIn('access', login_response.data)
        self.assertIn('refresh', login_response.data)
        send_otp.assert_not_called()

    @override_settings(TWO_FACTOR_LOGIN_ENABLED=True)
    def test_login_requires_otp_before_issuing_tokens_when_enabled(self):
        sent_otps = []

        def capture_otp(user, otp):
            sent_otps.append(otp)
            return True

        with patch('users.security_views.send_2fa_otp_email', side_effect=capture_otp):
            login_response = self.client.post(
                '/api/auth/login/',
                {
                    'email': self.user.email,
                    'password': 'StrongPass123!',
                },
                format='json',
            )

        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self.assertTrue(login_response.data['requires_2fa'])
        self.assertNotIn('access', login_response.data)
        self.assertNotIn('refresh', login_response.data)
        self.assertEqual(len(sent_otps), 1)

        otp_record = TwoFactorOTP.objects.get(user=self.user)
        self.assertEqual(otp_record.otp_code, hash_token(sent_otps[0]))
        self.assertNotEqual(otp_record.otp_code, sent_otps[0])

        verify_response = self.client.post(
            '/api/auth/verify-2fa-code/',
            {
                'email': self.user.email,
                'otp_code': sent_otps[0],
            },
            format='json',
        )

        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        self.assertIn('access', verify_response.data)
        self.assertIn('refresh', verify_response.data)
        otp_record.refresh_from_db()
        self.assertTrue(otp_record.used)

    def test_owner_can_enable_and_disable_2fa(self):
        owner = User.objects.create_user(
            username='owner2fa',
            email='owner2fa@example.com',
            password='StrongPass123!',
            email_verified=True,
        )
        org = Organization.objects.create(name='2FA Org')
        OrganizationMember.objects.create(user=owner, organization=org, role='OWNER')

        self.client.force_authenticate(owner)
        enable_response = self.client.post('/api/auth/enable-2fa/', {}, format='json')
        self.assertEqual(enable_response.status_code, status.HTTP_200_OK)
        owner.refresh_from_db()
        self.assertTrue(owner.two_factor_enabled)

        disable_response = self.client.post(
            '/api/auth/disable-2fa/',
            {'password': 'StrongPass123!'},
            format='json',
        )
        self.assertEqual(disable_response.status_code, status.HTTP_200_OK)
        owner.refresh_from_db()
        self.assertFalse(owner.two_factor_enabled)

    @override_settings(TWO_FACTOR_LOGIN_ENABLED=True)
    def test_google_login_requires_otp_for_2fa_enabled_existing_user_when_enabled(self):
        sent_otps = []

        def capture_otp(user, otp):
            sent_otps.append(otp)
            return True

        google_identity = {
            'email': self.user.email,
            'given_name': 'Two',
            'family_name': 'Factor',
        }

        with patch('users.views.GoogleLoginView._verify_google_credential', return_value=google_identity):
            with patch('users.security_views.send_2fa_otp_email', side_effect=capture_otp):
                response = self.client.post(
                    '/api/auth/google/',
                    {'credential': 'google-token'},
                    format='json',
                )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['requires_2fa'])
        self.assertNotIn('access', response.data)
        self.assertNotIn('refresh', response.data)
        self.assertEqual(len(sent_otps), 1)


class GetClientIPTestCase(TestCase):
    """Regression tests for get_client_ip — must always return a single string."""

    def _make_request(self, **meta):
        from django.test import RequestFactory
        rf = RequestFactory()
        request = rf.get('/')
        request.META.update(meta)
        return request

    def test_cloudflare_header(self):
        from users.utils import get_client_ip
        request = self._make_request(HTTP_CF_CONNECTING_IP='203.0.113.50')
        ip = get_client_ip(request)
        self.assertEqual(ip, '203.0.113.50')
        self.assertIsInstance(ip, str)

    def test_x_forwarded_for_single(self):
        from users.utils import get_client_ip
        request = self._make_request(HTTP_X_FORWARDED_FOR='198.51.100.1')
        ip = get_client_ip(request)
        self.assertEqual(ip, '198.51.100.1')

    def test_x_forwarded_for_multiple(self):
        from users.utils import get_client_ip
        request = self._make_request(HTTP_X_FORWARDED_FOR='198.51.100.1, 10.0.0.1, 172.16.0.1')
        ip = get_client_ip(request)
        self.assertEqual(ip, '198.51.100.1')
        self.assertNotIn(',', ip)

    def test_remote_addr_fallback(self):
        from users.utils import get_client_ip
        request = self._make_request(REMOTE_ADDR='127.0.0.1')
        ip = get_client_ip(request)
        self.assertEqual(ip, '127.0.0.1')

    def test_cf_takes_priority_over_forwarded_for(self):
        from users.utils import get_client_ip
        request = self._make_request(
            HTTP_CF_CONNECTING_IP='203.0.113.50',
            HTTP_X_FORWARDED_FOR='198.51.100.1, 10.0.0.1',
        )
        ip = get_client_ip(request)
        self.assertEqual(ip, '203.0.113.50')

    def test_no_headers_returns_none(self):
        from users.utils import get_client_ip
        from django.test import RequestFactory
        rf = RequestFactory()
        request = rf.get('/')
        # Remove REMOTE_ADDR so there are truly no IP headers
        request.META.pop('REMOTE_ADDR', None)
        ip = get_client_ip(request)
        self.assertIsNone(ip)
