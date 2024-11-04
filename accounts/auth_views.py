from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings
from datetime import datetime, timezone
from django.contrib.auth import authenticate

@api_view(["POST"])
def login(request):
    try:
        username = request.data.get("username")
        password = request.data.get("password")
        
        user = authenticate(username=username, password=password)
        if not user:
            return Response(
                {"detail": "Invalid credentials"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        
        response = Response({
            "access": access_token,
            "user": UserSerializer(user).data
        })
        
        # 개발 환경에서의 쿠키 설정
        cookie_settings = {
            'httponly': True,
            'samesite': None if settings.DEBUG else 'Lax',  # 개발 환경에서는 None
            'secure': not settings.DEBUG,  # 개발 환경에서는 False
            'path': '/',
            'max_age': 24 * 60 * 60,
        }
        
        if settings.DEBUG:
            # 개발 환경에서는 domain 설정 제거
            cookie_settings.pop('domain', None)
        
        response.set_cookie(
            'refresh_token',
            str(refresh),
            **cookie_settings
        )
        
        return response
        
    except Exception as e:
        print(f"Login error: {str(e)}")
        return Response(
            {"detail": "로그인에 실패했습니다."},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    try:
        # 리프레시 토큰을 쿠키에서 가져와서 블랙리스트에 추가
        refresh_token = request.COOKIES.get('refresh_token')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
            
        response = Response({"detail": "로그아웃되었습니다."})
        response.delete_cookie('refresh_token')  # 쿠키 삭제
        return response
    except Exception:
        return Response(
            {"detail": "로그아웃 처리 중 오류가 발생했습니다."},
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(["POST"])
def token_refresh(request):
    try:
        refresh_token = request.COOKIES.get('refresh_token')
        if not refresh_token:
            return Response(
                {"detail": "Refresh token not found"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        refresh = RefreshToken(refresh_token)
        
        if refresh.check_blacklist():
            return Response(
                {"detail": "Refresh token is blacklisted"}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
            
        access_token = str(refresh.access_token)
        
        response = Response({
            "access": access_token
        })
        
        if settings.SIMPLE_JWT['ROTATE_REFRESH_TOKENS']:
            refresh.blacklist()
            new_refresh = RefreshToken.for_user(refresh.get_user())
            
            cookie_settings = {
                'httponly': True,
                'samesite': None if settings.DEBUG else 'Lax',
                'secure': not settings.DEBUG,
                'path': '/',
                'max_age': 24 * 60 * 60,
            }
            
            if settings.DEBUG:
                cookie_settings.pop('domain', None)
            
            response.set_cookie(
                'refresh_token',
                str(new_refresh),
                **cookie_settings
            )
        
        return response
        
    except Exception as e:
        print(f"Token refresh error: {str(e)}")  # 디버깅용 로그 추가
        return Response(
            {"detail": "토큰 갱신에 실패했습니다."},
            status=status.HTTP_401_UNAUTHORIZED
        )
