"""
Security-related views for authentication enhancements
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import PasswordResetToken, TwoFactorOTP
from .auth_utils import (
    generate_token, generate_otp, send_verification_email,
    send_password_reset_email, send_2fa_otp_email, check_password_strength,
    blacklist_user_refresh_tokens, issue_refresh_token, hash_token
)
from .utils import get_client_ip
from .throttles import (
    AuthenticatedSecurityRateThrottle,
    OTPSendRateThrottle,
    OTPVerifyRateThrottle,
    PasswordResetConfirmRateThrottle,
    PasswordResetRequestRateThrottle,
    PasswordStrengthRateThrottle,
    ResendVerificationRateThrottle,
    VerifyEmailRateThrottle,
)

User = get_user_model()

EMAIL_VERIFICATION_MAX_AGE = timedelta(hours=24)



def send_two_factor_challenge(user, request):
    """Create and send a fresh email OTP for a 2FA-enabled user."""
    TwoFactorOTP.objects.filter(user=user, used=False).update(used=True)
    otp = generate_otp()
    TwoFactorOTP.objects.create(
        user=user,
        otp_code=hash_token(otp),
        ip_address=get_client_ip(request)
    )
    send_2fa_otp_email(user, otp)


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([ResendVerificationRateThrottle])
def resend_verification_email(request):
    """
    Resend email verification link
    POST /api/auth/resend-verification/
    """
    email = request.data.get('email')
    
    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(email=email)
        
        if user.email_verified:
            return Response(
                {'message': 'Email is already verified'},
                status=status.HTTP_200_OK
            )
        
        # Generate new token
        token = generate_token()
        user.email_verification_token = hash_token(token)
        user.email_verification_token_created_at = timezone.now()
        user.save(update_fields=['email_verification_token', 'email_verification_token_created_at'])
        
        # Send email
        send_verification_email(user, token)
        
        return Response({
            'message': 'Verification email sent successfully'
        })
        
    except User.DoesNotExist:
        # Don't reveal if email exists or not
        return Response({
            'message': 'If the email exists, a verification link has been sent'
        })


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([VerifyEmailRateThrottle])
def verify_email(request):
    """
    Verify email with token
    POST /api/auth/verify-email/
    """
    token = request.data.get('token')
    
    if not token:
        return Response(
            {'error': 'Token is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(email_verification_token=hash_token(token))
        
        if user.email_verified:
            return Response(
                {'message': 'Email is already verified'},
                status=status.HTTP_200_OK
            )

        issued_at = user.email_verification_token_created_at
        if not issued_at or issued_at < timezone.now() - EMAIL_VERIFICATION_MAX_AGE:
            user.email_verification_token = None
            user.email_verification_token_created_at = None
            user.save(update_fields=['email_verification_token', 'email_verification_token_created_at'])
            return Response(
                {'error': 'Invalid or expired verification token'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify email
        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_token_created_at = None
        user.save(update_fields=['email_verified', 'email_verification_token', 'email_verification_token_created_at'])
        
        return Response({
            'message': 'Email verified successfully'
        })
        
    except User.DoesNotExist:
        return Response(
            {'error': 'Invalid or expired verification token'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetRequestRateThrottle])
def request_password_reset(request):
    """
    Request password reset link
    POST /api/auth/request-password-reset/
    """
    email = request.data.get('email')
    
    if not email:
        return Response(
            {'error': 'Email is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        user = User.objects.get(email=email)
        
        # Generate token
        token = generate_token()
        token_hash = hash_token(token)

        # Invalidate older unused reset links for this account.
        PasswordResetToken.objects.filter(user=user, used=False).update(used=True)
        
        # Create password reset token
        PasswordResetToken.objects.create(
            user=user,
            token=token_hash
        )
        
        # Send email
        send_password_reset_email(user, token)
        
    except User.DoesNotExist:
        pass  # Don't reveal if email exists
    
    # Always return success to prevent email enumeration
    return Response({
        'message': 'If the email exists, a password reset link has been sent'
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordResetConfirmRateThrottle])
def reset_password(request):
    """
    Reset password with token
    POST /api/auth/reset-password/
    """
    token = request.data.get('token')
    new_password = request.data.get('new_password')
    
    if not token or not new_password:
        return Response(
            {'error': 'Token and new password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check password strength
    strength = check_password_strength(new_password)
    if strength['score'] < 2:
        return Response(
            {
                'error': 'Password is too weak',
                'feedback': strength['feedback']
            },
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        reset_token = PasswordResetToken.objects.select_related('user').get(token=hash_token(token))
        
        if not reset_token.is_valid():
            return Response(
                {'error': 'Token is invalid or expired'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Reset password
        user = reset_token.user
        user.set_password(new_password)
        user.failed_login_attempts = 0
        user.account_locked_until = None
        user.save()
        blacklist_user_refresh_tokens(user)
        
        # Mark token as used
        reset_token.used = True
        reset_token.save(update_fields=['used'])
        
        return Response({
            'message': 'Password reset successfully'
        })
        
    except PasswordResetToken.DoesNotExist:
        return Response(
            {'error': 'Invalid or expired token'},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([PasswordStrengthRateThrottle])
def check_password_strength_api(request):
    """
    Check password strength
    POST /api/auth/check-password-strength/
    """
    password = request.data.get('password')
    
    if not password:
        return Response(
            {'error': 'Password is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    strength = check_password_strength(password)
    return Response(strength)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthenticatedSecurityRateThrottle])
def enable_2fa(request):
    """
    Enable 2FA for user
    POST /api/auth/enable-2fa/
    """
    user = request.user
    
    from organizations.context import get_active_membership
    member = get_active_membership(user, request)

    if not member or member.role != 'OWNER':
        return Response(
            {'error': '2FA is only available for organization owners'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    user.two_factor_enabled = True
    user.save()
    
    return Response({
        'message': '2FA enabled successfully'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthenticatedSecurityRateThrottle])
def disable_2fa(request):
    """
    Disable 2FA for user
    POST /api/auth/disable-2fa/
    """
    user = request.user
    password = request.data.get('password')
    
    if not password:
        return Response(
            {'error': 'Password is required to disable 2FA'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if not user.check_password(password):
        return Response(
            {'error': 'Incorrect password'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    user.two_factor_enabled = False
    user.two_factor_secret = None
    user.save()
    
    return Response({
        'message': '2FA disabled successfully'
    })


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([OTPSendRateThrottle])
def send_2fa_code(request):
    """
    Send 2FA OTP code to user's email
    POST /api/auth/send-2fa-code/
    """
    username = request.data.get('username')
    email = request.data.get('email')
    password = request.data.get('password')
    
    if not (username or email) or not password:
        return Response(
            {'error': 'Email or username and password are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        if email:
            user = User.objects.get(email__iexact=email)
        else:
            user = User.objects.get(username=username)
        
        # Check if account is locked
        if user.account_locked_until and timezone.now() < user.account_locked_until:
            remaining = (user.account_locked_until - timezone.now()).seconds // 60
            return Response(
                {'error': f'Account is locked. Try again in {remaining} minutes'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Verify password
        if not user.check_password(password):
            user.failed_login_attempts += 1
            
            # Lock account after 5 failed attempts
            if user.failed_login_attempts >= 5:
                user.account_locked_until = timezone.now() + timedelta(minutes=15)
            
            user.save()
            
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if 2FA is enabled
        if not user.two_factor_enabled:
            return Response(
                {'error': '2FA is not enabled for this account'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        send_two_factor_challenge(user, request)
        
        return Response({
            'message': '2FA code sent to your email',
            'requires_2fa': True
        })
        
    except User.DoesNotExist:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )


@api_view(['POST'])
@permission_classes([AllowAny])
@throttle_classes([OTPVerifyRateThrottle])
def verify_2fa_code(request):
    """
    Verify 2FA OTP code and return JWT tokens
    POST /api/auth/verify-2fa-code/
    """
    username = request.data.get('username')
    email = request.data.get('email')
    otp_code = request.data.get('otp_code')
    remember_me = request.data.get('remember_me', False)
    
    if not (username or email) or not otp_code:
        return Response(
            {'error': 'Email or username and OTP code are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        if email:
            user = User.objects.get(email__iexact=email)
        else:
            user = User.objects.get(username=username)

        if not user.two_factor_enabled:
            return Response(
                {'error': '2FA is not enabled for this account'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find valid OTP
        otp = TwoFactorOTP.objects.filter(
            user=user,
            otp_code=hash_token(otp_code),
            used=False
        ).order_by('-created_at').first()
        
        if not otp or not otp.is_valid():
            return Response(
                {'error': 'Invalid or expired OTP code'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark OTP as used
        otp.used = True
        otp.save()
        
        # Reset failed login attempts
        user.failed_login_attempts = 0
        user.account_locked_until = None
        user.last_login_ip = get_client_ip(request)
        user.save()
        
        # Generate JWT tokens
        refresh_lifetime = settings.JWT_REMEMBER_ME_REFRESH_TOKEN_LIFETIME if remember_me else None
        refresh = issue_refresh_token(user, lifetime=refresh_lifetime)
        
        from .serializers import UserSerializer
        
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data
        })
        
    except User.DoesNotExist:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED
        )
