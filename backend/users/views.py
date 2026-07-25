import logging
import json
from datetime import timedelta
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token
from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from organizations.context import accept_invitation_for_user, build_workspace_payload
from organizations.models import Invitation
from .auth_utils import (
    check_password_strength,
    generate_token,
    hash_token,
    send_verification_email,
    EmailDeliveryError,
    blacklist_user_refresh_tokens,
    issue_refresh_token,
)
from .serializers import RegisterSerializer, UserSerializer
from .security_views import send_two_factor_challenge
from .utils import get_client_ip
from .throttles import (
    AuthenticatedSecurityRateThrottle,
    GoogleLoginRateThrottle,
    LoginRateThrottle,
    RegisterRateThrottle,
    TokenRefreshRateThrottle,
)

logger = logging.getLogger(__name__)

User = get_user_model()



class RegisterView(generics.CreateAPIView):
    """
    User registration endpoint with email verification.
    POST /api/auth/register/
    """
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer
    throttle_classes = [RegisterRateThrottle]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check password strength
        password = request.data.get('password')
        strength = check_password_strength(password)
        if strength['score'] < 2:
            return Response(
                {
                    'error': 'Password is too weak',
                    'feedback': strength['feedback']
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        invite_token = request.data.get('invite_token')
        if invite_token:
            try:
                invitation = Invitation.objects.get(
                    token=invite_token,
                    status='PENDING',
                    is_used=False,
                    expires_at__gt=timezone.now(),
                )
            except Invitation.DoesNotExist:
                raise ValidationError({'invite_token': 'Invalid or expired invitation link.'})
            invited_email = request.data.get('email', '').lower()
            if invited_email != invitation.email.lower():
                raise ValidationError({
                    'email': f'This invitation was sent to {invitation.email}. Please register with that email.'
                })

        try:
            with transaction.atomic():
                user = serializer.save()
                joined_org = None

                if invite_token:
                    member = accept_invitation_for_user(user, invite_token)
                    joined_org = {
                        'id': member.organization_id,
                        'name': member.organization.name,
                        'role': member.role,
                    }

                # Send the verification email before committing, so delivery
                # failures roll back the user and any invite membership.
                token = generate_token()
                user.email_verification_token = hash_token(token)
                user.email_verification_token_created_at = timezone.now()
                user.save(update_fields=['email_verification_token', 'email_verification_token_created_at'])
                send_verification_email(user, token, raise_on_failure=True)
        except EmailDeliveryError:
            logger.warning('Registration rolled back because verification email delivery failed.')
            return Response(
                {
                    'error': 'We could not send the verification email. Please try registering again in a moment.'
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        response_data = {
            'user': UserSerializer(user, context={'request': request}).data,
            'message': 'User registered successfully. Please check your email to verify your account.',
            **build_workspace_payload(user, request),
        }

        if joined_org:
            response_data['joined_organization'] = joined_org

        return Response(response_data, status=status.HTTP_201_CREATED)


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom login view with email, rate limiting, and remember me
    """
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        password = request.data.get('password')
        remember_me = request.data.get('remember_me', False)
        
        logger.info(f"Login attempt for email: {email}")
        
        if not email or not password:
            logger.warning(f"Login failed: missing email or password for email: {email}")
            return Response(
                {'error': 'Email and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email)
            logger.info(f"Found user: {user.username} for email: {email}")
            
            # Check if account is locked
            if user.account_locked_until and timezone.now() < user.account_locked_until:
                remaining = (user.account_locked_until - timezone.now()).seconds // 60
                logger.warning(f"Login failed: account locked for {remaining} minutes for user: {user.username}")
                return Response(
                    {'error': f'Account is locked due to multiple failed login attempts. Try again in {remaining} minutes.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Verify password
            if not user.check_password(password):
                user.failed_login_attempts += 1
                
                # Lock account after 5 failed attempts for 15 minutes
                if user.failed_login_attempts >= 5:
                    user.account_locked_until = timezone.now() + timedelta(minutes=15)
                    user.save()
                    logger.warning(f"Login failed: account locked after 5 attempts for user: {user.username}")
                    return Response(
                        {'error': 'Account locked due to multiple failed login attempts. Try again in 15 minutes.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                user.save()
                
                attempts_left = 5 - user.failed_login_attempts
                logger.warning(f"Login failed: invalid password for user: {user.username}, attempts left: {attempts_left}")
                return Response(
                    {
                        'error': 'Invalid email or password',
                        'attempts_left': attempts_left
                    },
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Check if email is verified
            if not user.email_verified:
                logger.warning(f"Login failed: email not verified for user: {user.username}")
                return Response(
                    {
                        'error': 'Please verify your email before logging in. Check your inbox for the verification link.',
                        'email_not_verified': True,
                        'email': user.email
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            
            # Reset failed login attempts
            user.failed_login_attempts = 0
            user.account_locked_until = None
            user.last_login_ip = get_client_ip(request)
            user.save()

            if settings.TWO_FACTOR_LOGIN_ENABLED and user.two_factor_enabled:
                send_two_factor_challenge(user, request)
                logger.info(f"2FA challenge sent for user: {user.username}")
                return Response({
                    'requires_2fa': True,
                    'email': user.email,
                    'message': 'Two-factor authentication code sent to your email',
                })
            
            # Generate JWT tokens
            refresh_lifetime = settings.JWT_REMEMBER_ME_REFRESH_TOKEN_LIFETIME if remember_me else None
            refresh = issue_refresh_token(user, lifetime=refresh_lifetime)
            
            logger.info(f"Login successful for user: {user.username}")
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': UserSerializer(user, context={'request': request}).data,
                'message': 'Login successful',
                **build_workspace_payload(user, request),
            })
            
        except User.DoesNotExist:
            logger.warning(f"Login failed: user not found for email: {email}")
            return Response(
                {'error': 'Invalid email or password'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class GoogleLoginView(APIView):
    """
    Google OAuth2 login and identity registration endpoint.
    POST /api/auth/google/
    """
    permission_classes = [AllowAny]
    throttle_classes = [GoogleLoginRateThrottle]

    def _verify_google_credential(self, credential):
        try:
            return id_token.verify_oauth2_token(
                credential,
                GoogleRequest(),
                audience=getattr(settings, "GOOGLE_CLIENT_ID", None),
            )
        except Exception:
            pass

        try:
            request = Request(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {credential}"},
            )
            with urlopen(request, timeout=5) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError):
            return None

    def post(self, request):
        credential = request.data.get("credential")
        remember_me = request.data.get("remember_me", False)
        
        if not credential:
            return Response(
                {"error": "credential is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        id_info = self._verify_google_credential(credential)
        if not id_info:
            return Response(
                {"error": "Invalid Google credential"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = (id_info.get("email") or "").strip().lower()
        if not email:
            return Response(
                {"error": "Google account email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        first_name = (id_info.get("given_name") or "").strip()
        last_name = (id_info.get("family_name") or "").strip()

        with transaction.atomic():
            # Check if user already exists
            user = User.objects.filter(email=email).first()
            
            if not user:
                # Resolve potential username conflicts by appending a short unique slug if needed
                username_base = email.split("@")[0] or "user"
                username = username_base
                while User.objects.filter(username=username).exists():
                    username = f"{username_base}_{uuid.uuid4().hex[:4]}"
                
                user = User.objects.create_user(
                    email=email,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    email_verified=True,  # Google emails are pre-verified
                )
                user.set_unusable_password()
                user.save()
            else:
                # Update empty details on existing profile if they match the Google profile data
                changed = False
                if not user.email_verified:
                    user.email_verified = True
                    changed = True
                if first_name and not user.first_name:
                    user.first_name = first_name
                    changed = True
                if last_name and not user.last_name:
                    user.last_name = last_name
                    changed = True
                if changed:
                    user.save()

            # Clear out any stale authentication lock logs since it's a social bypass
            user.failed_login_attempts = 0
            user.account_locked_until = None
            user.last_login_ip = get_client_ip(request)
            user.save()

            if settings.TWO_FACTOR_LOGIN_ENABLED and user.two_factor_enabled:
                send_two_factor_challenge(user, request)
                logger.info(f"2FA challenge sent for Google login user: {user.username}")
                return Response(
                    {
                        "requires_2fa": True,
                        "email": user.email,
                        "message": "Two-factor authentication code sent to your email",
                    },
                    status=status.HTTP_200_OK,
                )

            refresh_lifetime = settings.JWT_REMEMBER_ME_REFRESH_TOKEN_LIFETIME if remember_me else None
            refresh = issue_refresh_token(user, lifetime=refresh_lifetime)

        logger.info(f"Google Login successful for user: {user.username}")
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": UserSerializer(user, context={"request": request}).data,
                "message": "Login successful",
                **build_workspace_payload(user, request),
            },
            status=status.HTTP_200_OK,
        )


class ThrottledTokenRefreshView(TokenRefreshView):
    """Refresh-token endpoint with explicit abuse throttling."""
    throttle_classes = [TokenRefreshRateThrottle]


class CurrentUserView(generics.RetrieveAPIView):
    """
    Get current authenticated user.
    GET /api/auth/me/
    """
    serializer_class = UserSerializer
    
    def get_object(self):
        return self.request.user
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def retrieve(self, request, *args, **kwargs):
        user = self.get_object()
        data = UserSerializer(user, context={'request': request}).data
        data.update(build_workspace_payload(user, request))
        return Response(data)


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_profile(request):
    """
    Update user profile.
    PUT/PATCH /api/auth/profile/
    """
    user = request.user
    data = request.data
    
    # Update allowed fields
    if 'first_name' in data:
        user.first_name = data['first_name']
    if 'last_name' in data:
        user.last_name = data['last_name']
    if 'email' in data:
        # Check if email is already taken by another user
        if User.objects.filter(email=data['email']).exclude(id=user.id).exists():
            return Response(
                {'error': 'Email already in use'},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.email = data['email']
    if 'business_name' in data:
        user.business_name = data['business_name']
    if 'phone_number' in data:
        user.phone_number = data['phone_number']
    
    user.save()
    
    return Response({
        'user': UserSerializer(user, context={'request': request}).data,
        'message': 'Profile updated successfully'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([AuthenticatedSecurityRateThrottle])
def change_password(request):
    """
    Change user password.
    POST /api/auth/change-password/
    """
    user = request.user
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')
    
    if not old_password or not new_password:
        return Response(
            {'error': 'Both old and new passwords are required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify old password
    if not user.check_password(old_password):
        return Response(
            {'error': 'Current password is incorrect'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate new password length
    if len(new_password) < 8:
        return Response(
            {'error': 'New password must be at least 8 characters long'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Set new password
    user.set_password(new_password)
    user.save()
    blacklist_user_refresh_tokens(user)
    
    return Response({
        'message': 'Password changed successfully'
    })


@api_view(['PUT', 'PATCH'])
@permission_classes([IsAuthenticated])
def update_preferences(request):
    """
    Update user preferences.
    PUT/PATCH /api/auth/preferences/
    """
    user = request.user
    data = request.data
    
    # Update preference fields
    if 'default_currency' in data:
        if data['default_currency'] not in ['NPR', 'USD', 'EUR']:
            return Response(
                {'error': 'Invalid currency choice'},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.default_currency = data['default_currency']
    
    if 'items_per_page' in data:
        try:
            items = int(data['items_per_page'])
            if items not in [10, 20, 50, 100]:
                raise ValueError
            user.items_per_page = items
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid items per page value'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    if 'theme_preference' in data:
        if data['theme_preference'] not in ['light', 'dark', 'system']:
            return Response(
                {'error': 'Invalid theme preference'},
                status=status.HTTP_400_BAD_REQUEST
            )
        user.theme_preference = data['theme_preference']
    
    user.save()
    
    return Response({
        'user': UserSerializer(user, context={'request': request}).data,
        'message': 'Preferences updated successfully'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_profile_picture(request):
    """
    Upload or update user profile picture.
    POST /api/auth/upload-avatar/
    """
    user = request.user
    
    if 'profile_picture' not in request.FILES:
        return Response(
            {'error': 'No image file provided'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    profile_picture = request.FILES['profile_picture']
    
    # Validate file type
    allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp']
    if profile_picture.content_type not in allowed_types:
        return Response(
            {'error': 'Invalid file type. Only JPEG, PNG, GIF, and WebP images are allowed.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate file size (max 5MB)
    if profile_picture.size > 5 * 1024 * 1024:
        return Response(
            {'error': 'File size too large. Maximum size is 5MB.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Delete old profile picture if exists
    if user.profile_picture:
        user.profile_picture.delete(save=False)
    
    # Save new profile picture
    user.profile_picture = profile_picture
    user.save()
    
    serializer = UserSerializer(user, context={'request': request})
    
    return Response({
        'user': serializer.data,
        'message': 'Profile picture uploaded successfully'
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_profile_picture(request):
    """
    Delete user profile picture.
    DELETE /api/auth/delete-avatar/
    """
    user = request.user
    
    if not user.profile_picture:
        return Response(
            {'error': 'No profile picture to delete'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Delete the file
    user.profile_picture.delete(save=False)
    user.profile_picture = None
    user.save()
    
    serializer = UserSerializer(user, context={'request': request})
    
    return Response({
        'user': serializer.data,
        'message': 'Profile picture deleted successfully'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def export_user_data(request):
    """
    Export user's expense data as JSON.
    GET /api/auth/export-data/
    """
    from expenses.models import Expense
    from expenses.serializers import ExpenseSerializer
    
    user = request.user
    expenses = Expense.objects.filter(user=user)
    
    export_data = {
        'user': UserSerializer(user, context={'request': request}).data,
        'expenses': ExpenseSerializer(expenses, many=True).data,
        'export_date': user.updated_at.isoformat(),
        'total_expenses': expenses.count()
    }
    
    return Response(export_data)
